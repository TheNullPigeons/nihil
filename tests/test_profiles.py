from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from nihil.cli.controller import NihilController
from nihil.config.profiles import load_profile, save_profile


def test_profile_round_trip_and_cli_precedence(tmp_path):
    save_profile("redteam", {"image": "ad", "network": "docker", "privileged": True}, directory=tmp_path)
    profile = load_profile("redteam", directory=tmp_path)
    args = SimpleNamespace(
        image=None, network="nat", privileged=None, workspace_here=False,
    )

    NihilController._apply_profile(args, profile)

    assert args.image == "ad"
    assert args.network == "nat"
    assert args.privileged is True
    with pytest.raises(FileExistsError):
        save_profile("redteam", {}, directory=tmp_path)
    with pytest.raises(ValueError):
        save_profile("../escape", {}, directory=tmp_path)


def test_interactive_profile_creation(tmp_path, monkeypatch):
    import nihil.config.profiles as profiles

    monkeypatch.setattr(profiles, "NIHIL_HOME", tmp_path)
    controller = NihilController.__new__(NihilController)
    controller.config = SimpleNamespace(
        default_network="host", x11_by_default=True, wayland_by_default=True,
        my_resources_enabled=True, nihil_resources_enabled=True,
        logging_always_enable=False, default_shell="zsh",
    )
    controller.formatter = MagicMock()
    controller.formatter.success.side_effect = lambda value: value
    controller.formatter.info.side_effect = lambda value: value
    controller.formatter.error.side_effect = lambda value: value
    args = SimpleNamespace(
        profile_action="create", name=None, force=False, non_interactive=False,
        image=None, network=None, workspace=None, privileged=None, vpn=None,
        env=None, disable_x11=None, disable_wayland=None, no_my_resources=None,
        no_nihil_resources=None, browser_ui=None, browser_ui_port=None,
        log=None, tmux=None,
    )

    with (
        patch("rich.prompt.Prompt.ask", side_effect=["redteam", "ad", "docker", "", "", ""]),
        patch("rich.prompt.Confirm.ask", side_effect=[False, False, False, False, False, False, True, True]),
    ):
        assert controller._cmd_profile(args) == 0

    profile = load_profile("redteam", directory=tmp_path / "profiles")
    assert profile["image"] == "ad"
    assert profile["network"] == "docker"
    assert profile["log"] is True
    assert profile["tmux"] is True
