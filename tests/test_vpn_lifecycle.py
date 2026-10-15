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
def test_upgrade_checks_vpn_before_opening_shell(controller, vpn_flag):
    container = controller.manager.get_container.return_value
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
    args = create_parser().parse_args(["upgrade", "box", "--force", "--start"])

    assert controller._cmd_upgrade(args) == 0
    controller.manager.wait_for_vpn.assert_called_once_with(upgraded, timeout=2)
    controller._start_vpn_with_feedback.assert_called_once_with(upgraded)
    controller.manager.exec_in_container.assert_called_once_with(upgraded, "zsh")
