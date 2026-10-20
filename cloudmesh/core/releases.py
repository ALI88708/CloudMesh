"""Install CloudMesh from a verified GitHub release."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_REPO = "ALI88708/CloudMesh"
LTS_MIN = (4, 1, 0)
LTS_MAX = (4, 2, 0)

_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=100"
_VERSION_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)$")


class ReleaseError(RuntimeError):
    """A release could not be selected, verified, or installed."""


def parse_version(tag: str):
    """Return a three-part version tuple for a stable tag, or ``None``."""
    if not isinstance(tag, str):
        return None
    match = _VERSION_RE.fullmatch(tag.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def select_lts_release(releases):
    """Return the highest stable release in the supported 4.1.x line."""
    candidates = []
    for release in releases or []:
        if not isinstance(release, dict):
            continue
        version = parse_version(release.get("tag_name", ""))
        if version is None:
            continue
        if LTS_MIN <= version < LTS_MAX:
            candidates.append((version, release))
    if not candidates:
        raise ReleaseError("No 4.1.x release found")
    return max(candidates, key=lambda item: item[0])[1]


def _http_get(url: str) -> bytes:
    """Fetch a URL and return its bytes. This is the only network call."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "CloudMesh-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise ReleaseError(f"Could not reach {url}: {exc}") from exc


def fetch_releases():
    """Return the GitHub release list for the CloudMesh repository."""
    raw = _http_get(_RELEASES_URL)
    try:
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("GitHub returned an unreadable release list") from exc
    if not isinstance(payload, list):
        raise ReleaseError("GitHub returned an unexpected release list")
    return payload


def fetch_text(url: str) -> str:
    """Fetch a UTF-8 text asset."""
    raw = _http_get(url)
    try:
        return raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError as exc:
        raise ReleaseError(f"Could not decode {url} as UTF-8") from exc


def parse_sha256sums(text: str) -> dict[str, str]:
    """Map asset names to digests in a ``sha256sum``-style file."""
    sums = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts
        name = name.strip()
        if name.startswith("*"):
            name = name[1:]
        if name:
            sums[name] = digest.lower()
    return sums


def download_asset(url: str, dest) -> Path:
    """Download an asset to ``dest`` and return the local path."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _http_get(url)
    if isinstance(data, str):
        data = data.encode("utf-8")
    dest.write_bytes(data)
    return dest


def _pip_install(wheel) -> bool:
    """Install a local wheel with the interpreter running CloudMesh."""
    command = [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"pip could not start: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise ReleaseError(f"pip install failed: {detail}")
    return True


def _asset_by_name(release, predicate):
    for asset in release.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name", "")
        if not isinstance(name, str):
            continue
        if predicate(name):
            return asset
    return None


def update_from_github(dest_dir=None) -> str:
    """Download, verify, and install the newest 4.1.x GitHub release wheel."""
    release = select_lts_release(fetch_releases())
    tag = release.get("tag_name", "")
    version = tag[1:] if tag[:1] in ("v", "V") else tag

    wheel_asset = _asset_by_name(
        release,
        lambda name: name.startswith("cloudmesh-") and name.endswith(".whl")
        and Path(name).name == name,
    )
    sums_asset = _asset_by_name(release, lambda name: name == "SHA256SUMS")
    if wheel_asset is None:
        raise ReleaseError(f"No wheel asset found for CloudMesh {version}")
    if sums_asset is None:
        raise ReleaseError(f"SHA256SUMS asset missing for CloudMesh {version}")

    wheel_name = wheel_asset["name"]
    wheel_url = wheel_asset.get("browser_download_url", "")
    sums_url = sums_asset.get("browser_download_url", "")
    if not wheel_url or not sums_url:
        raise ReleaseError(f"Release assets for CloudMesh {version} are incomplete")

    if dest_dir is None:
        with tempfile.TemporaryDirectory(prefix="cloudmesh-update-") as temp:
            return _download_verify_install(
                version, wheel_name, wheel_url, sums_url, Path(temp)
            )
    work = Path(dest_dir)
    work.mkdir(parents=True, exist_ok=True)
    return _download_verify_install(
        version, wheel_name, wheel_url, sums_url, work
    )


def _download_verify_install(version, wheel_name, wheel_url, sums_url, work: Path) -> str:
    wheel_path = work / wheel_name

    expected = parse_sha256sums(fetch_text(sums_url)).get(wheel_name)
    if not expected:
        raise ReleaseError(f"SHA256SUMS has no checksum for {wheel_name}")

    download_asset(wheel_url, wheel_path)
    actual = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    if actual.lower() != expected:
        raise ReleaseError(f"checksum mismatch for {wheel_name}")

    _pip_install(str(wheel_path))
    return f"Updated to CloudMesh {version}"
