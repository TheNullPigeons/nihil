from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nihil.cli.controller import NihilController
from nihil.cli.parser import create_parser
from nihil.manager.manager import NihilManager
from nihil.utils.platform_info import DockerEngine


@pytest.mark.parametrize("ready", [True, False])
def test_legacy_start_waits_without_launching_openvpn(ready):
    manager = object.__new__(NihilManager)
    manager.wait_for_vpn = MagicMock(return_value=ready)
    container = MagicMock()
    container.attrs = {"Config": {"Env": ["NIHIL_VPN=1"]}}

    assert manager.start_vpn(container) is ready
    manager.wait_for_vpn.assert_called_once_with(container)
    container.exec_run.assert_not_called()


def test_managed_start_launches_openvpn():
    manager = object.__new__(NihilManager)
    manager.wait_for_vpn = MagicMock(return_value=True)
    container = MagicMock()
    container.attrs = {"Config": {"Env": ["NIHIL_VPN=managed"]}}

    assert manager.start_vpn(container) is True
    container.exec_run.assert_any_call(
        ["openvpn", "--log-append", "/var/log/nihil/vpn.log",
         "--config", "/opt/nihil/vpn/client.ovpn"], detach=True,
    )


def test_logged_shell_sets_recording_prompt_flag(controller):
    args = create_parser().parse_args(["start", "box", "--log"])

    assert controller._cmd_start(args) == 0

    command = controller.manager.exec_in_container.call_args.args[1]
    assert "asciinema rec" in command
    assert "--command 'NIHIL_SESSION_RECORDING=1 zsh'" in command


@pytest.fixture
def controller(monkeypatch):
    ctrl = object.__new__(NihilController)
    ctrl.config = SimpleNamespace(
        default_network="docker", x11_by_default=False, wayland_by_default=False,
        my_resources_enabled=False, nihil_resources_enabled=False,
        logging_always_enable=False, default_workspace=None,
        default_shell="zsh", auto_check_updates=False,
    )
    ctrl.formatter = MagicMock()
    ctrl.manager = MagicMock()
    container = ctrl.manager.get_container.return_value
    container.status = "exited"
    container.attrs = {"Config": {"Env": ["NIHIL_VPN=managed"]},
                       "HostConfig": {"NetworkMode": "bridge"}}
    ctrl.manager.wait_for_vpn.return_value = False
    ctrl._start_vpn_with_feedback = MagicMock()
    monkeypatch.setattr("nihil.utils.platform_info.get_docker_engine", lambda _: DockerEngine.NATIVE)
    return ctrl


@pytest.mark.parametrize("no_shell", [False, True])
def test_session_vpn_starts_once_with_or_without_shell(controller, tmp_path, no_shell):
    vpn = tmp_path / "client.ovpn"
    vpn.write_text("client\n")
    args = create_parser().parse_args(
        ["start", "box", "--vpn", str(vpn)] + (["--no-shell"] if no_shell else [])
    )
    assert controller._cmd_start(args) == 0
    container = controller.manager.get_container.return_value
    controller._start_vpn_with_feedback.assert_called_once_with(
        container, config_path="/tmp/nihil_vpn.ovpn",
    )
    assert controller.manager.exec_in_container.called is not no_shell
    if not no_shell:
        assert "killall openvpn" in controller.manager.exec_in_container.call_args.args[1]


@pytest.mark.parametrize("ready", [False, True])
def test_legacy_session_waits_for_entrypoint_before_replacement(controller, tmp_path, ready):
    vpn = tmp_path / "client.ovpn"
    vpn.write_text("client\n")
    container = controller.manager.get_container.return_value
    container.attrs["Config"]["Env"] = ["NIHIL_VPN=1"]
    controller.manager.wait_for_vpn.return_value = ready
    args = create_parser().parse_args(["start", "box", "--vpn", str(vpn), "--no-shell"])

    assert controller._cmd_start(args) == (0 if ready else 1)
    controller.manager.wait_for_vpn.assert_called_once_with(container)
    if ready:
        container.exec_run.assert_called_once_with(["killall", "openvpn"])
        controller._start_vpn_with_feedback.assert_called_once()
    else:
        container.exec_run.assert_not_called()
        controller.manager.copy_file_into_container.assert_not_called()
        controller._start_vpn_with_feedback.assert_not_called()


@pytest.mark.parametrize("vpn_flag", ["managed", "1"])
@pytest.mark.parametrize("status", ["running", "exited"])
@pytest.mark.parametrize("start", [False, True])
def test_upgrade_checks_vpn_before_opening_shell(controller, vpn_flag, status, start):
    container = controller.manager.get_container.return_value
    container.status = status
    controller.manager.snapshot_container_config.return_value = {
        "name": "box", "image": "nihil/full:latest", "privileged": False,
        "volumes": {}, "network_mode": "bridge",
        "environment": {"NIHIL_VPN": vpn_flag},
    }
    controller.manager.refresh_display_forwarding.return_value = False
    controller.manager.extract_container_data.return_value = {}
    controller.manager._variant_for_image_tag.return_value = None
    controller._resolve_display_forwarding = MagicMock(return_value=(False, False, []))
    upgraded = controller.manager.recreate_container.return_value
    upgraded.status = "running"
    upgraded.attrs = {"Config": {"Env": [f"NIHIL_VPN={vpn_flag}"]}}
    args = create_parser().parse_args(["upgrade", "box", "--force"] + (["--start"] if start else []))

    assert controller._cmd_upgrade(args) == 0
    if status == "running" or start:
        controller.manager.start_container.assert_called_once_with(upgraded)
        controller.manager.wait_for_vpn.assert_called_once_with(upgraded, timeout=2)
        controller._start_vpn_with_feedback.assert_called_once_with(upgraded)
    else:
        controller.manager.start_container.assert_not_called()
        controller.manager.wait_for_vpn.assert_not_called()
        controller._start_vpn_with_feedback.assert_not_called()
    if start:
        controller.manager.exec_in_container.assert_called_once_with(upgraded, "zsh")
    else:
        controller.manager.exec_in_container.assert_not_called()


def _vpn_container(cid, name, digest, running_config="/opt/nihil/vpn/client.ovpn", tun=True):
    container = MagicMock()
    container.id, container.name = cid, name
    container.attrs = {"HostConfig": {"Devices": [{"PathOnHost": "/dev/net/tun"}] if tun else None}}

    def exec_run(cmd, **_):
        if cmd[0] == "pgrep":
            if running_config is None:
                return 1, b""
            return 0, f"42 openvpn --log-append /var/log/nihil/vpn.log --config {running_config}\n".encode()
        if cmd[0] == "sha256sum":
            return (0, f"{digest}  {cmd[1]}\n".encode()) if digest else (1, b"")
        return 0, b""

    container.exec_run.side_effect = exec_run
    return container


def test_find_vpn_conflicts_reports_other_containers_with_same_config():
    manager = object.__new__(NihilManager)
    target = _vpn_container("t", "target", "abc", running_config=None)
    others = [
        target,
        _vpn_container("a", "same", "abc", running_config="/tmp/nihil_vpn.ovpn"),
        _vpn_container("b", "different", "def"),
        _vpn_container("c", "vpn-down", "abc", running_config=None),
        _vpn_container("d", "no-tun", "abc", tun=False),
    ]
    manager.list_containers = MagicMock(return_value=others)

    assert manager.find_vpn_conflicts(target, "/opt/nihil/vpn/client.ovpn") == ["same"]
    manager.list_containers.assert_called_once_with(all=False)


def test_find_vpn_conflicts_skips_scan_when_config_unreadable():
    manager = object.__new__(NihilManager)
    manager.list_containers = MagicMock()
    target = _vpn_container("t", "target", None)

    assert manager.find_vpn_conflicts(target, "/opt/nihil/vpn/client.ovpn") == []
    manager.list_containers.assert_not_called()


@pytest.mark.parametrize("conflicts", [[], ["other"]])
def test_start_vpn_warns_on_conflicting_config(conflicts):
    ctrl = object.__new__(NihilController)
    ctrl.formatter = MagicMock()
    ctrl.manager = MagicMock()
    ctrl.manager.find_vpn_conflicts.return_value = conflicts
    ctrl.manager.start_vpn.return_value = True
    ctrl._loading = MagicMock()
    container = MagicMock()

    ctrl._start_vpn_with_feedback(container)

    ctrl.manager.find_vpn_conflicts.assert_called_once_with(container, "/opt/nihil/vpn/client.ovpn")
    assert ctrl.formatter.warning.called == bool(conflicts)
    if conflicts:
        assert "other" in ctrl.formatter.warning.call_args.args[0]
    ctrl.manager.start_vpn.assert_called_once()
