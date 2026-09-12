import socket

from desktop_launcher import InstanceLock, bind_local_port


def test_second_instance_cannot_take_lock_until_first_exits(tmp_path):
    first, second = InstanceLock(tmp_path), InstanceLock(tmp_path)
    try:
        assert first.acquire()
        assert not second.acquire()
        first.close()
        assert second.acquire()
    finally:
        first.close()
        second.close()


def test_occupied_port_uses_another_loopback_port():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        with bind_local_port(occupied.getsockname()[1]) as available:
            assert available.getsockname()[0] == "127.0.0.1"
            assert available.getsockname()[1] != occupied.getsockname()[1]


def test_data_directory_override_seeds_a_blank_profile(tmp_path, monkeypatch):
    import json

    import paths

    monkeypatch.setenv("STFC_ADVISOR_DATA_DIR", str(tmp_path / "fresh"))
    target = paths.profile_path()
    assert target.parent == tmp_path / "fresh"
    assert json.loads(target.read_text())["officers"] == []
