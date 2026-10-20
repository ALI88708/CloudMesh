import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_soak_harness_runs_a_short_cycle(tmp_path):
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
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "soak passed" in process.stdout.lower()
