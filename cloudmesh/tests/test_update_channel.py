from pathlib import Path

import pytest

from core import releases


def _release(tag, assets):
    return {"tag_name": tag, "assets": assets}


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_select_lts_release_ignores_4_2_and_prereleases():
    payload = [
        _release("v4.2.0", []),
        _release("v4.1.3-rc.1", []),
        _release("v4.1.2", []),
        _release("v4.1.1", []),
    ]
    assert releases.select_lts_release(payload)["tag_name"] == "v4.1.2"


def test_select_lts_release_rejects_a_line_with_no_4_1_release():
    with pytest.raises(releases.ReleaseError):
        releases.select_lts_release([_release("v4.2.0", [])])


def test_update_fails_closed_without_checksums(monkeypatch, tmp_path):
    release = _release(
        "v4.1.2",
        [
            {"name": "cloudmesh-4.1.2-py3-none-any.whl", "browser_download_url": "https://x/w.whl"},
        ],
    )
    monkeypatch.setattr(releases, "fetch_releases", lambda: [release])
    monkeypatch.setattr(releases, "download_asset", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not download")))
    with pytest.raises(releases.ReleaseError, match="SHA256SUMS"):
        releases.update_from_github(dest_dir=tmp_path)


def test_update_rejects_a_checksum_mismatch(monkeypatch, tmp_path):
    release = _release(
        "v4.1.2",
        [
            {"name": "cloudmesh-4.1.2-py3-none-any.whl", "browser_download_url": "https://x/w.whl"},
            {"name": "SHA256SUMS", "browser_download_url": "https://x/SHA256SUMS"},
        ],
    )
    monkeypatch.setattr(releases, "fetch_releases", lambda: [release])
    monkeypatch.setattr(releases, "fetch_text", lambda _url: "deadbeef  cloudmesh-4.1.2-py3-none-any.whl\n")
    monkeypatch.setattr(releases, "download_asset", lambda _url, dest: _write(dest, b"wheel"))
    monkeypatch.setattr(releases, "_pip_install", lambda _wheel: pytest.fail("pip must not run"))
    with pytest.raises(releases.ReleaseError, match="checksum"):
        releases.update_from_github(dest_dir=tmp_path)


def test_update_installs_only_the_verified_local_wheel(monkeypatch, tmp_path):
    wheel = b"wheel-bytes"
    digest = __import__("hashlib").sha256(wheel).hexdigest()
    release = _release(
        "v4.1.2",
        [
            {"name": "cloudmesh-4.1.2-py3-none-any.whl", "browser_download_url": "https://x/w.whl"},
            {"name": "SHA256SUMS", "browser_download_url": "https://x/SHA256SUMS"},
        ],
    )
    monkeypatch.setattr(releases, "fetch_releases", lambda: [release])
    monkeypatch.setattr(releases, "fetch_text", lambda _url: f"{digest}  cloudmesh-4.1.2-py3-none-any.whl\n")
    monkeypatch.setattr(releases, "download_asset", lambda _url, dest: _write(dest, wheel))
    seen = {}
    monkeypatch.setattr(releases, "_pip_install", lambda path: seen.update(path=Path(path)) or True)
    assert "4.1.2" in releases.update_from_github(dest_dir=tmp_path)
    assert seen["path"].name == "cloudmesh-4.1.2-py3-none-any.whl"


def test_documentation_has_no_pypi_cloudmesh_command():
    for name in ("README.md", "CONTRIBUTING.md", "site/index.html"):
        text = (Path(__file__).resolve().parent.parent.parent / name).read_text(encoding="utf-8")
        assert "pip install cloudmesh" not in text
        assert "pip install --upgrade cloudmesh" not in text
