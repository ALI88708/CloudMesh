import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_soak_harness_runs_a_short_cycle(tmp_path):
    """The harness runs for two seconds; the timeout is a hang guard.

    It is not a performance bound: the harness starts an interpreter,
    imports the package, and opens a database, and on a loaded runner that
    startup alone can take a minute. A 60-second guard turned a slow
    machine into a failure of the release gate, so the guard is wide
    enough to survive a busy runner and still catch a hang.
    """
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "soak_test.py"),
            "--duration", "2",
            "--interval", "0.2",
            "--workspace", str(tmp_path / "soak"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "soak passed" in process.stdout.lower()
