"""Local fingerprint boundaries and failures for directory synchronization."""

import hashlib
from unittest.mock import Mock

import pytest

from core import sync


@pytest.mark.parametrize("size", [0, 1, 8191, 8192, 8193, 24577])
def test_md5_fingerprints_binary_files_across_chunk_boundaries(tmp_path, size):
    content = (b"\x00\xff\r\nabc" * (size // 7 + 1))[:size]
    path = tmp_path / "binary data.bin"
    path.write_bytes(content)

    fingerprint = sync.DirectorySync(None)._md5(path)

    assert fingerprint == hashlib.md5(content).hexdigest()
    assert len(fingerprint) == 32
    assert path.read_bytes() == content


def test_md5_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        sync.DirectorySync(None)._md5(tmp_path / "missing")


def test_md5_read_error_propagates_and_closes_file(monkeypatch):
    from unittest.mock import mock_open

    failure = OSError("read failed")
    reader = mock_open()
    reader.return_value.read.side_effect = failure
    monkeypatch.setattr(sync, "open", reader, raising=False)

    with pytest.raises(OSError) as exc:
        sync.DirectorySync(None)._md5("unreadable.bin")

    assert exc.value is failure
    reader.return_value.__exit__.assert_called_once()


def test_md5_unavailable_algorithm_error_propagates(monkeypatch):
    failure = ValueError("MD5 is unavailable")
    monkeypatch.setattr(sync.hashlib, "md5", Mock(side_effect=failure))

    with pytest.raises(ValueError) as exc:
        sync.DirectorySync(None)._md5("unused.bin")

    assert exc.value is failure
