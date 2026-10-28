import argparse

import pytest

from cloudmesh.core.wait import unmet_conditions, wait_for_conditions


def metrics(cpu=10.0, ram=20.0, disk=30.0):
    return {
        "cpu_percent": cpu,
        "ram": {"percent": ram},
        "disk": {"percent": disk},
    }


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Sequence:
    """Collector that walks through samples and repeats the last one."""

    def __init__(self, *samples):
        self.samples = list(samples)
        self.calls = []

    def __call__(self, name):
        self.calls.append(name)
        sample = self.samples.pop(0) if len(self.samples) > 1 else self.samples[0]
        if isinstance(sample, Exception):
            raise sample
        return sample


def test_only_the_metrics_over_the_threshold_are_reported():
    assert unmet_conditions(metrics(cpu=91, ram=10), {"cpu": 90, "ram": 90}) == {
        "cpu": (91.0, 90)
    }


def test_a_value_exactly_on_the_threshold_counts_as_satisfied():
    assert unmet_conditions(metrics(cpu=90), {"cpu": 90}) == {}


def test_a_metric_the_target_did_not_report_counts_as_unmet():
    assert unmet_conditions({"ram": {"percent": 5}}, {"cpu": 50, "ram": 90}) == {
        "cpu": (None, 50)
    }


def test_an_unchecked_metric_is_ignored():
    assert unmet_conditions(metrics(cpu=99, ram=10), {"cpu": None, "ram": 50}) == {}


def test_wait_returns_on_the_first_satisfied_sample():
    clock = FakeClock()
    collector = Sequence(metrics(cpu=10))

    result = wait_for_conditions(
        collector, ["web-1"], {"cpu": 50}, timeout=60, interval=5,
        clock=clock.time, sleep=clock.sleep,
    )

    assert result["satisfied"] is True
    assert result["attempts"] == 1
    assert collector.calls == ["web-1"]
    assert clock.sleeps == []


def test_wait_polls_until_the_condition_holds():
    clock = FakeClock()
    collector = Sequence(metrics(cpu=95), metrics(cpu=40))

    result = wait_for_conditions(
        collector, ["web-1"], {"cpu": 50}, timeout=60, interval=5,
        clock=clock.time, sleep=clock.sleep,
    )

    assert result["satisfied"] is True
    assert result["attempts"] == 2
    assert clock.sleeps == [5]


def test_wait_times_out_and_keeps_the_last_observation():
    clock = FakeClock()
    collector = Sequence(metrics(cpu=95))

    result = wait_for_conditions(
        collector, ["web-1"], {"cpu": 50}, timeout=12, interval=5,
        clock=clock.time, sleep=clock.sleep,
    )

    assert result["satisfied"] is False
    assert result["elapsed_seconds"] >= 12
    assert result["unmet"] == {"web-1": {"cpu": (95.0, 50)}}


def test_a_collection_error_does_not_crash_the_wait():
    clock = FakeClock()
    collector = Sequence(OSError("connection refused"), metrics(cpu=10))

    result = wait_for_conditions(
        collector, ["web-1"], {"cpu": 50}, timeout=60, interval=5,
        clock=clock.time, sleep=clock.sleep,
    )

    assert result["satisfied"] is True
    assert result["attempts"] == 2


def test_every_target_has_to_satisfy_the_condition():
    clock = FakeClock()
    collector = Sequence(metrics(cpu=10), metrics(cpu=90), metrics(cpu=10), metrics(cpu=20))

    result = wait_for_conditions(
        collector, ["web-1", "web-2"], {"cpu": 50}, timeout=60, interval=5,
        clock=clock.time, sleep=clock.sleep,
    )

    assert result["satisfied"] is True
    assert result["attempts"] == 2


def test_no_condition_is_rejected():
    clock = FakeClock()
    try:
        wait_for_conditions(
            Sequence(metrics()), ["web-1"], {"cpu": None}, timeout=60, interval=5,
            clock=clock.time, sleep=clock.sleep,
        )
    except ValueError:
        return
    raise AssertionError("a wait without a condition must be rejected")


def test_no_target_is_rejected():
    clock = FakeClock()
    try:
        wait_for_conditions(
            Sequence(metrics()), [], {"cpu": 50}, timeout=60, interval=5,
            clock=clock.time, sleep=clock.sleep,
        )
    except ValueError:
        return
    raise AssertionError("a wait without targets must be rejected")


class _Servers:
    def __init__(self, names):
        self.names = names

    def list_servers(self):
        return self.names


class _Monitor:
    def __init__(self, sample):
        self.sample = sample

    def get_all_metrics(self, name):
        return self.sample

    def get_local_metrics(self):
        return self.sample


def _wait_args(**overrides):
    base = {
        "name": None, "local": False, "cpu_below": None, "ram_below": None,
        "disk_below": None, "timeout": 60, "interval": 5,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _wire(monkeypatch, monitor, servers=("web-1",)):
    import cloudmesh.main as main_module

    monkeypatch.setattr(
        main_module,
        "init_components",
        lambda: (None, _Servers(list(servers)), monitor),
    )
    return main_module


def test_cm_wait_without_a_condition_exits_2(monkeypatch):
    main_module = _wire(monkeypatch, _Monitor(metrics(cpu=1)))

    with pytest.raises(SystemExit) as exc:
        main_module.cmd_wait(_wait_args())

    assert exc.value.code == 2


def test_cm_wait_exits_0_when_the_condition_holds(monkeypatch):
    main_module = _wire(monkeypatch, _Monitor(metrics(cpu=5)))

    main_module.cmd_wait(_wait_args(cpu_below=50))


def test_cm_wait_exits_1_on_timeout(monkeypatch):
    main_module = _wire(monkeypatch, _Monitor(metrics(cpu=99)))
    monkeypatch.setattr(
        main_module,
        "wait_for_conditions",
        lambda *a, **k: {
            "satisfied": False,
            "attempts": 3,
            "elapsed_seconds": 60.0,
            "unmet": {"web-1": {"cpu": (99.0, 50)}},
            "errors": {},
            "conditions": {"cpu": 50},
        },
    )

    with pytest.raises(SystemExit) as exc:
        main_module.cmd_wait(_wait_args(cpu_below=50))

    assert exc.value.code == 1
