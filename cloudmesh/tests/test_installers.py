"""Contracts the installers must keep.

Neither installer had any check of its own, so a CRLF file, a blanked package
file, and a dependency list missing `bcrypt` all shipped. These assertions are
cheap and run on every platform in the ordinary suite; the workflows in
`.github/workflows/installers.yml` then do the real install.

The bugs pinned here, in order of severity:

1. Both `.sh` files were committed with CRLF endings, so `bash cm_for-linux.sh`
   died with a syntax error on line one. The one-line Linux install in the
   README could never run.
2. `cm_for-windows.bat` ran `echo. > ...\\core\\__init__.py`, replacing the
   package re-exports with a single blank line.
3. The Windows installer installed five hard-coded packages and omitted
   `bcrypt`, which pyproject declares, so ACL commands raised ImportError on
   any machine installed that way.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
LINUX_INSTALLER = ROOT / "cm_for-linux.sh"
WINDOWS_INSTALLER = ROOT / "cm_for-windows.bat"
NODE_SH = ROOT / "cloudmesh" / "node" / "node-install.sh"
PYPROJECT = ROOT / "pyproject.toml"

# Directories that hold third-party code; their shell scripts are not ours to
# police (and `.gitignore` already lists several of them).
_SKIP_DIRS = {
    ".git", ".verify-venv", ".rel-venv", "venv", ".venv", "build", "dist",
    "node_modules", ".tox", ".mypy_cache", ".pytest_cache",
}

SHELL_SCRIPTS = sorted(
    p
    for p in ROOT.glob("**/*.sh")
    if not (_SKIP_DIRS & set(p.relative_to(ROOT).parts))
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _find_bash() -> str | None:
    """Return a bash that understands native Windows paths, or None.

    `shutil.which("bash")` happily returns the WSL launcher, which cannot see
    C:\\ paths at all, so a syntax check through it fails for the wrong reason.
    """
    candidates = [shutil.which("bash")]
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.exists():
        candidates.insert(0, str(git_bash))
    for candidate in candidates:
        if not candidate:
            continue
        if "system32" in candidate.lower():
            continue  # WSL bash
        return candidate
    return None


# --- line endings -------------------------------------------------------


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_shell_scripts_use_lf_endings(script):
    """CRLF makes bash fail on the first line, so the Linux install never ran."""
    data = script.read_bytes()
    assert b"\r\n" not in data, (
        f"{script.name} has CRLF line endings; bash cannot parse it on Linux"
    )


def test_gitattributes_pins_shell_scripts_to_lf():
    """Without this rule the endings drift back the moment someone edits."""
    attributes = ROOT / ".gitattributes"
    assert attributes.exists(), ".gitattributes is missing"
    text = _text(attributes)
    assert re.search(r"\*\.sh\s+text\s+eol=lf", text), (
        ".gitattributes must pin *.sh to LF"
    )
    assert re.search(r"\*\.bat\s+text\s+eol=crlf", text), (
        ".gitattributes must keep *.bat on CRLF"
    )


def test_linux_installer_is_committed_executable():
    """The README flow is `chmod +x cm.sh && ./cm.sh`; CI runs it directly too.

    Committed as 100644 this fails with exit 126 on Linux, which is what the
    first installer run in CI hit.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "-s", "--", str(LINUX_INSTALLER), str(NODE_SH)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    if tracked.returncode != 0 or not tracked.stdout.strip():
        pytest.skip("not a git checkout")
    for line in tracked.stdout.strip().splitlines():
        mode, _sha, _stage, path = line.split(maxsplit=3)
        assert mode == "100755", (
            f"{path} is committed as {mode}; a shell script needs 100755 "
            "for './cm.sh' to run"
        )


def test_shell_scripts_are_syntactically_valid():
    bash = _find_bash()
    if not bash:
        pytest.skip("no native bash on this platform; CI runs this on ubuntu-latest")
    for script in (LINUX_INSTALLER, NODE_SH):
        if not script.exists():
            continue
        result = subprocess.run(
            [bash, "-n", str(script)], capture_output=True, text=True, timeout=60
        )
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


# --- Windows installer --------------------------------------------------


def test_windows_installer_does_not_blank_core_init():
    """It used to run `echo. > core\\__init__.py`, wiping the re-exports."""
    text = _text(WINDOWS_INSTALLER)
    offenders = [
        line
        for line in text.splitlines()
        if re.search(r">\s*\"?%CLOUDMESH_DIR%\\core\\__init__\.py", line, re.I)
    ]
    assert not offenders, f"core/__init__.py is overwritten: {offenders}"


def test_core_init_is_not_empty():
    """The file the installer used to truncate must actually carry imports."""
    init = ROOT / "cloudmesh" / "core" / "__init__.py"
    assert init.stat().st_size > 10, "core/__init__.py is suspiciously small"
    assert "import" in _text(init), "core/__init__.py carries no imports"


def test_windows_installer_installs_the_project_not_a_dependency_list():
    """A hand-written list omitted bcrypt, which pyproject declares."""
    text = _text(WINDOWS_INSTALLER)
    assert 'pip install --quiet "%PROJECT_DIR%"' in text, (
        "the Windows installer must pip-install the project directory"
    )
    # A bare `pip install a b c` line is the pattern that drifted before. Only
    # actual command lines count, not the log messages that mention pip.
    offenders = [
        line.strip()
        for line in text.splitlines()
        if re.match(r'\s*"?%VENV_PYTHON%"?\s+-m\s+pip\s+install\s+(?!-)(?!["%])\S', line)
    ]
    assert not offenders, f"installer hard-codes a dependency list: {offenders}"


def test_declared_dependencies_are_all_importable():
    """Anything pyproject declares must exist, or a clean install is broken."""
    declared = re.findall(
        r'"([A-Za-z0-9_.-]+)\s*[><=~!]', re.search(r"dependencies\s*=\s*\[(.*?)\]", _text(PYPROJECT), re.S).group(1)
    )
    # Map distribution names onto the modules that prove they installed.
    probes = {
        "psutil": "psutil",
        "rich": "rich",
        "cryptography": "cryptography",
        "paramiko": "paramiko",
        "pycryptodome": "Crypto",
        "bcrypt": "bcrypt",
    }
    for dist in declared:
        module = probes.get(dist)
        if not module:
            continue
        __import__(module)


# --- scripted (non-interactive) mode ------------------------------------


@pytest.mark.parametrize(
    "path, markers",
    [
        (LINUX_INSTALLER, ["NONINTERACTIVE", "--yes", "verify_install"]),
        (WINDOWS_INSTALLER, ["NONINTERACTIVE", "/Y", "verify_install"]),
    ],
    ids=["linux", "windows"],
)
def test_installer_supports_a_scripted_path(path, markers):
    """An interactive-only installer cannot be verified by CI at all."""
    text = _text(path)
    for marker in markers:
        assert marker in text, f"{path.name} has no {marker!r} support"


@pytest.mark.parametrize(
    "path", [LINUX_INSTALLER, WINDOWS_INSTALLER], ids=["linux", "windows"]
)
def test_installer_verifies_the_result(path):
    """Reporting success once files land is how a broken install looked clean."""
    text = _text(path)
    for probe in ("cm --version", "--help"):
        assert probe in text, f"{path.name} never checks {probe!r}"
    assert "pip install" in text or "pip_install" in text


def test_linux_installer_help_does_not_require_a_tty():
    bash = _find_bash()
    if not bash:
        pytest.skip("no native bash on this platform; CI runs this on ubuntu-latest")
    result = subprocess.run(
        [bash, str(LINUX_INSTALLER), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr
    assert "--verify-only" in result.stdout


def test_linux_installer_parses_the_project_layout():
    """pyproject declares packages = ["cloudmesh", ...], so pip needs a
    directory that CONTAINS the package, not the package itself."""
    text = _text(LINUX_INSTALLER)
    assert 'PROJECT_DIR="$INSTALL_DIR/project"' in text
    assert 'CLOUDMESH_DIR="$PROJECT_DIR/cloudmesh"' in text
    assert 'pip install --quiet "$PROJECT_DIR"' in text


def test_windows_installer_parses_the_project_layout():
    text = _text(WINDOWS_INSTALLER)
    assert 'set "CLOUDMESH_DIR=%PROJECT_DIR%\\cloudmesh"' in text
    assert 'pip install --quiet "%PROJECT_DIR%"' in text


@pytest.mark.skipif(sys.platform == "win32", reason="batch installer is for Windows")
def test_windows_installer_is_not_executed_on_posix():
    """Nothing to run here; the file is still linted by the contract tests."""
    assert WINDOWS_INSTALLER.exists()


# --- the Linux one-liner in the README ----------------------------------


def test_readme_linux_install_command_matches_the_installer():
    """The README tells users to curl and run the installer; keep them in sync."""
    readme = _text(ROOT / "README.md")
    match = re.search(r"raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/(\S+\.sh)", readme)
    assert match, "README no longer documents a curl-based Linux install"
    assert (ROOT / match.group(1)).exists(), f"README points at missing {match.group(1)}"


# Exercise the changed shell blocks without invoking downloads, pip or systemd.
def _installer_block(pattern):
    match = re.search(pattern, _text(LINUX_INSTALLER), re.S | re.M)
    assert match, "Installer structure changed; update the shell test harness"
    return match.group(1)


def _run_installer_block(tmp_path, block, helpers=""):
    bash = _find_bash()
    if not bash or sys.platform == "win32":
        pytest.skip("installer filesystem tests require POSIX bash")
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    script = '''
set -e
INSTALL_DIR="$1/install with spaces"
PROJECT_DIR="$INSTALL_DIR/project"
CLOUDMESH_DIR="$PROJECT_DIR/cloudmesh"
LEGACY_CLOUDMESH_DIR="$INSTALL_DIR/cloudmesh"
NODE_DIR="$1/node"
VENV_DIR="$INSTALL_DIR/venv"
PAYLOAD_DIR="$1/payload"
log() { :; }
fail() { echo "$*" >&2; return 1; }
''' + helpers + "\n" + block
    result = subprocess.run(
        [bash, "-c", script, "installer-test", str(tmp_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=5,
        env={**os.environ, "TMPDIR": str(scratch)},
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.parametrize(
    "current_files, legacy_files",
    [
        ([], []),
        ([".node_keys.json", ".secret.key"], []),
        ([], [".node_keys.json", ".secret.key"]),
        ([".node_keys.json", ".secret.key"], [".node_keys.json", ".secret.key"]),
        ([".node_keys.json"], [".secret.key"]),
        ([".secret.key"], [".node_keys.json"]),
        ([], [".secret.key"]),
        ([".node_keys.json"], []),
    ],
    ids=["no-state", "current", "legacy", "current-wins", "split-key",
         "split-nodes", "secret-only", "nodes-only"],
)
def test_linux_update_preserves_state(tmp_path, current_files, legacy_files):
    install = tmp_path / "install with spaces"
    current = install / "project" / "cloudmesh"
    legacy = install / "cloudmesh"
    expected = {}
    for directory, names in [(legacy, legacy_files), (current, current_files)]:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "main.py").write_text("old version")
        for name in names:
            path = directory / name
            data = f"{directory.relative_to(install)}:{name}".encode()
            path.write_bytes(data)
            path.chmod(0o600)
            os.utime(path, (1_600_000_000, 1_600_000_000))
            expected[name] = data
    config = install / "cloudmesh.json"
    config.write_text('{"servers": {"saved": {}}}')
    config.chmod(0o600)
    payload = tmp_path / "payload"
    (payload / "cloudmesh").mkdir(parents=True)
    (payload / "cloudmesh" / "main.py").write_text("new version")
    (payload / "pyproject.toml").write_text("[project]\nname = 'fixture'\n")
    stage = _installer_block(r"^(stage_payload\(\) \{.*?^\})")
    update = _installer_block(r'case "\$CHOICE" in\s+1\)(.*?)\n\s+;;')
    helpers = stage + '''
fetch_payload() { stage_payload "$PAYLOAD_DIR"; }
do_setup() { cp -a "$CLOUDMESH_DIR" "$INSTALL_DIR/state-at-setup"; }
ui_pause() { exit 0; }
'''

    _run_installer_block(tmp_path, "while true; do\n" + update + "\nbreak\ndone", helpers)

    assert (current / "main.py").read_text() == "new version"
    assert not legacy.exists()
    assert config.read_text() == '{"servers": {"saved": {}}}'
    assert config.stat().st_mode & 0o777 == 0o600
    for name in (".node_keys.json", ".secret.key"):
        if name in expected:
            assert (current / name).read_bytes() == expected[name]
            assert (install / "state-at-setup" / name).read_bytes() == expected[name]
            assert (current / name).stat().st_mode & 0o777 == 0o600
            assert (current / name).stat().st_mtime == 1_600_000_000
        else:
            assert not (current / name).exists()
    assert list((tmp_path / "scratch").iterdir()) == []


def test_linux_update_fetch_failure_keeps_existing_state(tmp_path):
    install = tmp_path / "install with spaces"
    originals = {}
    for layout in ("project/cloudmesh", "cloudmesh"):
        directory = install / layout
        directory.mkdir(parents=True)
        for name in ("main.py", ".node_keys.json", ".secret.key"):
            path = directory / name
            path.write_text(f"original {layout}/{name}")
            originals[path] = path.read_bytes()
    update = _installer_block(r'case "\$CHOICE" in\s+1\)(.*?)\n\s+;;')
    helpers = '''
fetch_payload() { return 1; }
do_setup() { touch "$INSTALL_DIR/setup-ran"; }
ui_pause() { exit 0; }
'''

    _run_installer_block(tmp_path, "while true; do\n" + update + "\nbreak\ndone", helpers)

    assert not (install / "setup-ran").exists()
    for path, data in originals.items():
        assert path.read_bytes() == data
    assert list((tmp_path / "scratch").iterdir()) == []


@pytest.mark.parametrize("layout", [None, "cloudmesh", "project/cloudmesh", "venv"])
def test_linux_install_detection_supports_both_layouts(tmp_path, layout):
    install = tmp_path / "install with spaces"
    if layout:
        directory = install / layout
        directory.mkdir(parents=True)
        if layout != "venv":
            (directory / "main.py").touch()
    detection = _installer_block(r'^(IS_INSTALLED=0\n.*?if \[ -d "\$VENV_DIR" \]; then.*?^fi)')

    result = _run_installer_block(tmp_path, detection + '\necho "$IS_INSTALLED"')

    assert result.stdout.strip() == ("1" if layout else "0")


@pytest.mark.parametrize("layouts", [["cloudmesh"], ["project"], ["cloudmesh", "project"]])
def test_linux_uninstall_removes_both_program_layouts(tmp_path, layouts):
    install = tmp_path / "install with spaces"
    for layout in layouts:
        directory = install / layout
        directory.mkdir(parents=True)
        (directory / "old-secret").write_text("synthetic secret")
    config = install / "cloudmesh.json"
    config.write_text("keep config")
    cleanup = _installer_block(r'^do_uninstall\(\) \{(.*?)\n    if command -v systemctl')

    _run_installer_block(tmp_path, cleanup + "\ntrue")

    assert not (install / "project").exists()
    assert not (install / "cloudmesh").exists()
    assert config.read_text() == "keep config"
