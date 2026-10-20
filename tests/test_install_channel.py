from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from nihil.cli.controller import NihilController
from nihil.config.user_config import NihilConfig


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setattr("nihil.config.user_config.CONFIG_FILE", tmp_path / "config.yml")
    controller = NihilController.__new__(NihilController)
    controller.config = NihilConfig()
    controller.manager = MagicMock()
    controller.formatter = MagicMock()
    controller._login_personal_registry = MagicMock()
    return controller


@pytest.mark.parametrize("image", ["ad", None])
@pytest.mark.parametrize("source,channel,interactive,accept,expected,prompted", [
    ("upstream", "main", True, "y", "dev", True),
    ("upstream", "main", True, "n", "main", True),
    ("upstream", "main", False, "y", "main", False),
    ("upstream", "dev", True, "y", "dev", False),
    ("personal", "main", True, "y", "main", False),
])
def test_install_channel(controller, image, source, channel, interactive, accept, expected, prompted):
    controller.config._data["image_sources"].update(
        active=source, channel=channel, personal_repo="tester/nihil-images", personal_branch="custom"
    )
    controller.config.save()
    controller._configure_image_registry()
    with patch("sys.stdin.isatty", return_value=interactive), \
         patch("rich.prompt.Prompt.ask", return_value=accept) as confirm, \
         patch("rich.prompt.IntPrompt.ask", return_value=2):
        assert controller._cmd_install(SimpleNamespace(image=image)) == 0
    if prompted:
        confirm.assert_called_once()
        assert confirm.call_args.kwargs["default"] == "n"
        assert confirm.call_args.kwargs["choices"] == ["y", "n", "never"]
    else:
        confirm.assert_not_called()
    assert NihilConfig().image_channel == expected
    assert NihilConfig().prompt_for_dev is True
    tag = "dev" if expected == "dev" else "latest"
    reference = "ghcr.io/tester/ad:custom" if source == "personal" else f"ghcr.io/thenullpigeons/ad:{tag}"
    controller.manager._pull_with_progress.assert_called_once_with(reference)


@pytest.mark.parametrize("error", [KeyboardInterrupt, EOFError])
def test_cancel_channel_prompt_does_not_pull_or_change_config(controller, error):
    controller._configure_image_registry()
    with patch("sys.stdin.isatty", return_value=True), \
         patch("rich.prompt.Prompt.ask", side_effect=error):
        assert controller._cmd_install(SimpleNamespace(image="ad")) == 0
    controller.manager._pull_with_progress.assert_not_called()
    assert NihilConfig().image_channel == "main"


def test_invalid_variant_does_not_prompt_or_change_channel(controller):
    controller._configure_image_registry()
    with patch("sys.stdin.isatty", return_value=True), patch("rich.prompt.Prompt.ask") as confirm:
        assert controller._cmd_install(SimpleNamespace(image="invalid")) == 1
    confirm.assert_not_called()
    controller.manager._pull_with_progress.assert_not_called()
    assert NihilConfig().image_channel == "main"


def test_never_is_saved_and_skips_future_prompts(controller):
    controller._configure_image_registry()
    with patch("sys.stdin.isatty", return_value=True), \
         patch("rich.prompt.Prompt.ask", return_value="never") as prompt:
        assert controller._cmd_install(SimpleNamespace(image="ad")) == 0
        prompt.assert_called_once()
        controller.config = NihilConfig()
        assert controller.config.image_channel == "main"
        assert controller.config.prompt_for_dev is False
        prompt.reset_mock()
        assert controller._cmd_install(SimpleNamespace(image="ad")) == 0
        prompt.assert_not_called()
    assert controller.manager._pull_with_progress.call_count == 2
    for call in controller.manager._pull_with_progress.call_args_list:
        assert call.args == ("ghcr.io/thenullpigeons/ad:latest",)
