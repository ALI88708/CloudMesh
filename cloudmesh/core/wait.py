"""Polling until resource conditions hold.

`cm wait` exists so a CI job or a cron entry can say "run this once the box
is quiet" without re-implementing a polling loop in shell. The interesting
part is not the loop but the contract: one sample never satisfies two
targets, a target that cannot be reached is not a satisfied target, and a
wait that has no condition to check is a mistake rather than an infinite
loop.
"""

from time import monotonic, sleep as _sleep

DEFAULT_TIMEOUT = 300
DEFAULT_INTERVAL = 10

# thresholds keys are the CLI flag names; the monitor nests two of them.
METRIC_PATHS = {
    "cpu": ("cpu_percent",),
    "ram": ("ram", "percent"),
    "disk": ("disk", "percent"),
}


def _metric_value(metrics, name):
    path = METRIC_PATHS[name]
    node = metrics
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if node is None or isinstance(node, bool):
        return None
    try:
        return float(node)
    except (TypeError, ValueError):
        return None


def unmet_conditions(metrics, thresholds):
    """Return {metric: (observed, threshold)} for every condition that fails.

    A metric the target did not report is unmet, not satisfied: silence is
    how an unreachable box looks, and waiting on it should not succeed.
    """
    unmet = {}
    if not isinstance(metrics, dict):
        metrics = {}
    for name, threshold in thresholds.items():
        if threshold is None:
            continue
        value = _metric_value(metrics, name)
        if value is None or value > threshold:
            unmet[name] = (value, threshold)
    return unmet


def _validated(thresholds, targets, timeout, interval):
    if not isinstance(targets, (list, tuple)) or not targets:
        raise ValueError("At least one target is required")
    checked = {
        name: limit for name, limit in thresholds.items() if limit is not None
    }
    unknown = set(checked) - set(METRIC_PATHS)
    if unknown:
        raise ValueError(f"Unknown condition(s): {', '.join(sorted(unknown))}")
    if not checked:
        raise ValueError(
            "Nothing to wait for: pass --cpu-below, --ram-below or --disk-below"
        )
    for name, value in checked.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"The {name} threshold must be a number")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("Timeout must be a positive number of seconds")
    if not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval <= 0:
        raise ValueError("Interval must be a positive number of seconds")


def wait_for_conditions(collector, targets, thresholds, timeout=DEFAULT_TIMEOUT,
                        interval=DEFAULT_INTERVAL, clock=monotonic, sleep=_sleep):
    """Poll every target until all conditions hold or the timeout expires.

    The first sample is taken immediately, so a box that is already quiet
    returns without sleeping. A target that raises is retried on the next
    pass rather than aborting the wait, because a machine that is rebooting
    is exactly the machine a wait is usually pointed at.
    """
    _validated(thresholds, targets, timeout, interval)
    started = clock()
    attempts = 0
    unmet = {}
    errors = {}
    while True:
        attempts += 1
        unmet = {}
        errors = {}
        for target in targets:
            try:
                metrics = collector(target)
            except Exception as exc:
                errors[target] = str(exc) or exc.__class__.__name__
                continue
            failed = unmet_conditions(metrics, thresholds)
            if failed:
                unmet[target] = failed
        if not unmet and not errors:
            return {
                "satisfied": True,
                "attempts": attempts,
                "elapsed_seconds": clock() - started,
                "unmet": {},
                "errors": {},
                "conditions": {k: v for k, v in thresholds.items() if v is not None},
            }
        elapsed = clock() - started
        if elapsed >= timeout:
            return {
                "satisfied": False,
                "attempts": attempts,
                "elapsed_seconds": elapsed,
                "unmet": unmet,
                "errors": errors,
                "conditions": {k: v for k, v in thresholds.items() if v is not None},
            }
        sleep(min(interval, timeout - elapsed))
