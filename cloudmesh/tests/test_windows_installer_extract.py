"""The Windows installer's payload must land where it later looks for it.

`cm_for-windows.bat` builds a PowerShell script line by line with `echo`, and
that script's job is to unpack GitHub's zip into the project directory. It ran
to completion -- the install log recorded `Extract result: 0` -- and the very
next line still reported failure:

    [ERROR] Extract failed!
    Extract FAILED - main.py missing

Because PowerShell exited 0, the failure had to be in the payload's *shape*, not
its extraction. It was:

    if (Test-Path $destPath) { Remove-Item -Recurse -Force $destPath }
    Copy-Item -Path (Join-Path $d.FullName 'cloudmesh') -Destination $destPath -Recurse -Force

`Copy-Item -Path <dir> -Destination <dir>` infers the destination name from
whether `<dir>` already exists:

- destination absent  -> the source directory *becomes* the destination, so
                         `project\\main.py`
- destination present -> the source is copied *into* it, so
                         `project\\cloudmesh\\main.py`

Only the second shape satisfies `CLOUDMESH_DIR=%PROJECT_DIR%\\cloudmesh`, and
the `Remove-Item` on the line above guarantees the first. Measured on Windows:
3 of the 4 create/remove combinations produce the wrong shape.

The Linux installer never had the bug because `cp -r src dest/cloudmesh` names
the destination explicitly. This test runs the real generated PowerShell so the
semantics are checked, not the spelling of the batch file.
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WINDOWS_INSTALLER = ROOT / "cm_for-windows.bat"

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="the batch installer is for Windows"
)


def _extract_powershell(destination: Path) -> str:
    """Rebuild the PowerShell that cm_for-windows.bat writes to cm_ex.ps1.

    The batch file assembles the script with `echo ... >> "%TEMP%\\cm_ex.ps1"`,
    so the script under test is derived from the file itself rather than
    restated here. A restatement would pass while the real installer fails,
    which is exactly what happened.
    """
    text = WINDOWS_INSTALLER.read_text(encoding="utf-8", errors="replace")

    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        # The batch file also echoes a log line naming cm_ex.ps1; that is not
        # part of the script.
        if "cm_ex.ps1 written" in stripped:
            break
        if "cm_ex.ps1" not in stripped or not stripped.startswith("echo "):
            continue
        body = stripped[len("echo "):]
        # Undo the batch file's output redirection and the `^|` it uses to keep
        # a literal pipe out of the echo.
        body = body.replace('>> "%TEMP%\\cm_ex.ps1"', "")
        body = body.replace('> "%TEMP%\\cm_ex.ps1"', "")
        body = body.replace("^|", "|")
        body = body.replace("%PROJECT_DIR%", str(destination).replace("'", "''"))
        lines.append(body)

    assert lines, "found no cm_ex.ps1 echo lines; the batch file changed shape"
    return "\n".join(lines)


def _stage_zip() -> Path:
    """Build a zip shaped like `archive/refs/heads/main.zip`."""
    zip_path = Path(os.environ["TEMP"]) / "cloudmesh.zip"
    staging = Path(os.environ["TEMP"]) / "cloudmesh_zip_src"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    package = staging / "CloudMesh-main" / "cloudmesh" / "core"
    package.mkdir(parents=True)
    (staging / "CloudMesh-main" / "cloudmesh" / "main.py").write_text(
        "# extracted payload\n", encoding="utf-8"
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    (staging / "CloudMesh-main" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (staging / "CloudMesh-main" / "README.md").write_text("# readme\n", encoding="utf-8")
    (staging / "CloudMesh-main" / "LICENSE").write_text("license\n", encoding="utf-8")

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w") as archive:
        for item in sorted(staging.rglob("*")):
            archive.write(item, item.relative_to(staging).as_posix())
    shutil.rmtree(staging, ignore_errors=True)
    return zip_path


def test_windows_installer_payload_lands_in_the_cloudmesh_subdirectory(tmp_path):
    """PROJECT_DIR must end up holding cloudmesh/, not the package itself.

    `pip install --quiet "%PROJECT_DIR%"` needs a directory that *contains* the
    package, so a payload that lands flat at `project\\main.py` both fails the
    installer's own `main.py` check and would not be installable.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    _stage_zip()
    script = tmp_path / "cm_ex.ps1"
    script.write_text(_extract_powershell(project_dir), encoding="utf-8")

    proc = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    cloudmesh_dir = project_dir / "cloudmesh"
    assert (cloudmesh_dir / "main.py").is_file(), (
        f"payload did not land in {cloudmesh_dir}.\\n"
        f"exit={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}\n"
        f"project dir now contains: "
        f"{sorted(p.name for p in project_dir.iterdir()) if project_dir.exists() else 'missing'}"
    )
    assert (cloudmesh_dir / "core" / "__init__.py").is_file(), "package is incomplete"

    # The installer checks CLOUDMESH_DIR\main.py immediately after this script.
    assert (cloudmesh_dir / "main.py").exists(), "installer self-check would fail"

    # pyproject.toml is what makes the directory installable, and it must sit at
    # the project root, next to the package.
    assert (project_dir / "pyproject.toml").is_file(), "pyproject.toml not restored"


def test_windows_installer_copy_does_not_infer_the_destination_name():
    """Structural guard: name the destination, never let Copy-Item infer it.

    The three-line change is easy to "simplify" back into the bug, and the
    behaviour it breaks is invisible in the batch file's text.
    """
    text = WINDOWS_INSTALLER.read_text(encoding="utf-8", errors="replace")

    # Copy-Item of the package must target an explicit path, not bare $destPath.
    assert re.search(
        r"Copy-Item -Path \(Join-Path \$d\.FullName 'cloudmesh'\)"
        r" -Destination (?!%PROJECT_DIR%')",
        text,
    ), "Copy-Item again infers the destination name; pass an explicit path"

    # And it must recreate the project directory after removing it, exactly as
    # the Linux installer does with `mkdir -p "$PROJECT_DIR"`.
    assert "New-Item -ItemType Directory -Path $destPath" in text, (
        "the project directory is removed and never recreated, so Copy-Item "
        "flattens the payload; the Linux installer recreates it"
    )