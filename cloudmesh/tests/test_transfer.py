"""Recursive uploads use local fixtures and mocked SSH/SFTP connections."""

import shlex
from unittest.mock import Mock

import pytest

from core.transfer import FileTransfer


def test_upload_directory_preserves_relative_paths_and_file_contents(tmp_path):
    source = tmp_path / "source"
    nested = source / "nested folder"
    nested.mkdir(parents=True)
    (source / "empty folder").mkdir()
    files = {"root.txt": b"root", "nested folder/data.bin": b"\x00\xffpayload"}
    for name, content in files.items():
        (source / name).write_bytes(content)
    remote = "/srv/uploads with 'quotes'; echo unsafe"
    sftp = Mock()
    client = Mock()
    client.open_sftp.return_value = sftp
    manager = Mock()
    manager.connect.return_value = client

    results = FileTransfer(manager).upload_directory("target", str(source), remote)

    uploaded = {}
    for call in sftp.put.call_args_list:
        local, destination = call.args
        relative = str(local)[len(str(source)) + 1:].replace("\\", "/")
        assert destination == f"{remote}/{relative}"
        uploaded[relative] = (source / relative).read_bytes()
    assert uploaded == files
    assert sftp.close.call_count == len(files)
    assert len(results) == len(files)
    assert {result["message"] for result in results} == {
        f"Uploaded to target:{remote}/{name}" for name in files
    }
    assert all(result["success"] is True for result in results)
    assert {call.args[0] for call in client.exec_command.call_args_list} == {
        f"mkdir -p {shlex.quote(remote)}",
        f"mkdir -p {shlex.quote(remote + '/nested folder')}",
    }
    assert all(call.args == ("target",) for call in manager.connect.call_args_list)


@pytest.mark.parametrize("exists", [False, True], ids=["missing", "empty"])
def test_upload_directory_without_files_does_not_connect(tmp_path, exists):
    source = tmp_path / "source"
    if exists:
        source.mkdir()
    manager = Mock()

    assert FileTransfer(manager).upload_directory("target", str(source), "/srv") == []
    manager.connect.assert_not_called()


@pytest.mark.parametrize("failure", ["connect", "mkdir"])
def test_upload_directory_still_uploads_when_directory_creation_fails(tmp_path, failure):
    source_file = tmp_path / "data.txt"
    source_file.write_text("payload", encoding="utf-8")
    manager = Mock()
    if failure == "connect":
        manager.connect.side_effect = OSError("connection unavailable")
    else:
        manager.connect.return_value.exec_command.side_effect = OSError("already exists")
    transfer = FileTransfer(manager)
    transfer.upload = Mock(return_value={"success": True})

    assert transfer.upload_directory("target", str(tmp_path), "/srv") == [{"success": True}]
    transfer.upload.assert_called_once_with("target", str(source_file), "/srv/data.txt")


def test_upload_directory_propagates_upload_failure_and_preserves_earlier_uploads(
    tmp_path, monkeypatch
):
    from core import transfer as transfer_mod

    for name in ["first.txt", "second.txt", "third.txt"]:
        (tmp_path / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr(
        transfer_mod.os, "walk",
        lambda _path: [(str(tmp_path), [], ["first.txt", "second.txt", "third.txt"])],
    )
    sftp = Mock()
    failure = OSError("SFTP write failed")
    sftp.put.side_effect = [None, failure]
    manager = Mock()
    manager.connect.return_value.open_sftp.return_value = sftp

    with pytest.raises(OSError) as exc:
        FileTransfer(manager).upload_directory("target", str(tmp_path), "/srv")

    assert exc.value is failure
    assert [call.args[1] for call in sftp.put.call_args_list] == [
        "/srv/first.txt", "/srv/second.txt"
    ]
    assert sftp.close.call_count == 2
    sftp.remove.assert_not_called()
