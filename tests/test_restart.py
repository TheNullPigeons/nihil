from types import SimpleNamespace
from unittest.mock import MagicMock

from docker.errors import APIError
import pytest

from nihil.cli.controller import NihilController
from nihil.cli.parser import create_parser
from nihil.exceptions import ContainerStartFailed, ContainerStopFailed


@pytest.fixture
def controller():
    ctrl = object.__new__(NihilController)
    ctrl.config = SimpleNamespace(default_shell="zsh")
    ctrl.formatter = MagicMock()
    ctrl.manager = MagicMock()
    ctrl._start_vpn_with_feedback = MagicMock()
    ctrl.manager.get_container.return_value = SimpleNamespace(
        status="running", attrs={"Config": {"Env": []}},
    )
    return ctrl


@pytest.mark.parametrize("argv,names,no_shell", [
    (["box"], ["box"], False),
    (["box", "lab"], ["box", "lab"], False),
    (["box", "--no-shell"], ["box"], True),
])
def test_parser(argv, names, no_shell):
    args = create_parser().parse_args(["restart", *argv])
    assert args.command == "restart"
    assert args.names == names
    assert args.no_shell is no_shell


def test_parser_requires_a_name():
    with pytest.raises(SystemExit):
        create_parser().parse_args(["restart"])


@pytest.mark.parametrize("status", ["running", "exited"])
def test_restart_running_or_stopped_container(controller, status):
    container = controller.manager.get_container.return_value
    container.status = status
    assert controller._cmd_restart(SimpleNamespace(names=["box"], no_shell=True)) == 0
    assert controller.manager.stop_container.called == (status == "running")
    controller.manager.start_container.assert_called_once_with(container)
    controller.manager.exec_in_container.assert_not_called()


@pytest.mark.parametrize("shell,command", [
    ("zsh", "zsh"), ("bash", "bash"), ("tmux", "tmux new-session -A -s nihil"),
])
def test_single_restart_opens_configured_shell(controller, shell, command):
    controller.config.default_shell = shell
    assert controller._cmd_restart(SimpleNamespace(names=["box"], no_shell=False)) == 0
    controller.manager.exec_in_container.assert_called_once_with(
        controller.manager.get_container.return_value, command,
    )


@pytest.mark.parametrize("flag,ready", [(None, False), ("1", False), ("managed", False), ("managed", True)])
def test_vpn_restart(controller, flag, ready):
    container = controller.manager.get_container.return_value
    container.attrs["Config"]["Env"] = [f"NIHIL_VPN={flag}"] if flag else []
    controller.manager.wait_for_vpn.return_value = ready
    assert controller._cmd_restart(SimpleNamespace(names=["box"], no_shell=True)) == 0
    if flag:
        controller.manager.wait_for_vpn.assert_called_once_with(container, timeout=2)
    else:
        controller.manager.wait_for_vpn.assert_not_called()
    assert controller._start_vpn_with_feedback.called == bool(flag and not ready)


def test_multiple_restarts_do_not_open_a_shell(controller):
    assert controller._cmd_restart(SimpleNamespace(names=["box", "lab"], no_shell=False)) == 0
    assert controller.manager.start_container.call_count == 2
    controller.manager.exec_in_container.assert_not_called()


def test_missing_container_does_not_block_the_next_or_open_a_shell(controller):
    container = controller.manager.get_container.return_value
    controller.manager.get_container.side_effect = [None, container]
    assert controller._cmd_restart(SimpleNamespace(names=["missing", "lab"], no_shell=False)) == 1
    controller.manager.start_container.assert_called_once_with(container)
    controller.manager.exec_in_container.assert_not_called()


@pytest.mark.parametrize("method,error", [
    ("stop_container", ContainerStopFailed(name="box")),
    ("start_container", ContainerStartFailed(name="box")),
    ("get_container", APIError("Docker unavailable")),
])
def test_failure_does_not_abort_remaining_restarts(controller, method, error):
    result = controller.manager.get_container.return_value if method == "get_container" else True
    getattr(controller.manager, method).side_effect = [error, result]
    assert controller._cmd_restart(SimpleNamespace(names=["box", "lab"], no_shell=False)) == 1
    assert controller.manager.get_container.call_count == 2
    controller.formatter.error.assert_called_once()
    controller.formatter.success.assert_called_once()
    controller.manager.exec_in_container.assert_not_called()
