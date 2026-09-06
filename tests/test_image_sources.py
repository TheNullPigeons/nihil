from pathlib import Path
import json
import pytest
from types import SimpleNamespace

from nihil.cli.parser import create_parser
from nihil.features.image_sources import ImageSourceManager


def test_image_commands_are_available():
    parser = create_parser()

    customize = parser.parse_args(["image", "customize", "web", "--no-push"])
    assert customize.command == "image"
    assert customize.image_action == "customize"
    assert customize.variant == "web"
    assert customize.no_push is True
    assert customize.repo is None
    assert customize.git_protocol == "ssh"
    assert customize.git_del is False

    https = parser.parse_args(["image", "customize", "web", "--git-protocol", "https"])
    assert https.git_protocol == "https"

    delete = parser.parse_args(["image", "customize", "web", "--git-del"])
    assert delete.git_del is True

    switch = parser.parse_args(["image", "switch", "personal"])
    assert switch.image_action == "switch"
    assert switch.source == "personal"

    build = parser.parse_args(["image", "build", "web", "--wait"])
    assert build.image_action == "build"
    assert build.variant == "web"
    assert build.wait is True


def test_repository_urls_are_normalized(tmp_path):
    config = SimpleNamespace(image_sources_home=tmp_path)
    manager = ImageSourceManager(config, upstream_repo="https://github.com/acme/security-images.git")
    assert manager.upstream_repo == "acme/security-images"


def test_existing_fork_is_reused_and_custom_branch_is_created(tmp_path):
    home = tmp_path / "sources"
    path = home / "alice" / "nihil-images"
    (path / ".git").mkdir(parents=True)

    config = SimpleNamespace(
        image_sources_home=home,
        image_sources_upstream_path=home / "upstream" / "nihil-images",
    )
    saved = {}

    def set_image_source(**kwargs):
        saved.update(kwargs)

    config.set_image_source = set_image_source
    manager = ImageSourceManager(config)

    calls = []

    def fake_run(command, *, cwd=None, capture=True):
        calls.append(command)
        if command[:3] == ["gh", "api", "user"]:
            return "alice"
        if command[:4] == ["gh", "repo", "view", "alice/nihil-images"]:
            return "name"
        if command == ["git", "remote"]:
            return "origin\nupstream"
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            return "https://github.com/alice/nihil-images.git"
        if command[:4] == ["git", "remote", "get-url", "upstream"]:
            return "https://github.com/TheNullPigeons/nihil-images.git"
        if command[:2] == ["git", "branch"]:
            return ""
        if command[:4] == ["gh", "repo", "view", "TheNullPigeons/nihil-images"]:
            return "main"
        return ""

    manager._run = fake_run
    result_path, repo, branch = manager.ensure_personal_fork(variant="web")

    assert result_path == path
    assert repo == "alice/nihil-images"
    assert branch == "nihil/web-custom"
    assert saved == {}
    assert ["gh", "repo", "fork", "TheNullPigeons/nihil-images", "--clone=false"] not in calls
    assert ["git", "switch", "-c", "nihil/web-custom", "upstream/main"] in calls


def test_existing_remote_custom_branch_is_checked_out_after_local_reset(tmp_path):
    home = tmp_path / "sources"
    path = home / "alice" / "nihil-images"
    config = SimpleNamespace(
        image_sources_home=home,
        image_sources_upstream_path=home / "upstream" / "nihil-images",
    )
    config.set_image_source = lambda **kwargs: None
    manager = ImageSourceManager(config)
    calls = []

    def fake_run(command, *, cwd=None, capture=True):
        calls.append(command)
        if command[:3] == ["gh", "api", "user"]:
            return "alice"
        if command[:4] == ["gh", "repo", "view", "alice/nihil-images"]:
            return "name"
        if command == ["git", "remote"]:
            return "origin\nupstream"
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            return "git@github.com:alice/nihil-images.git"
        if command[:4] == ["git", "remote", "get-url", "upstream"]:
            return "git@github.com:TheNullPigeons/nihil-images.git"
        if command[:2] == ["git", "branch"] and "--remotes" in command:
            return "origin/main\norigin/nihil/web-custom"
        if command[:2] == ["git", "branch"]:
            return "main"
        if command[:4] == ["gh", "repo", "view", "TheNullPigeons/nihil-images"]:
            return "main"
        return ""

    manager._run = fake_run
    manager.ensure_personal_fork(variant="web", delete_existing=True)

    assert [
        "git", "switch", "-c", "nihil/web-custom", "--track", "origin/nihil/web-custom"
    ] in calls


def test_trigger_build_dispatches_and_can_wait(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        personal_image_repo="alice/nihil-images",
        personal_image_branch="nihil/web-custom",
    )
    manager = ImageSourceManager(config)
    calls = []

    def fake_run(command, *, cwd=None, capture=True):
        calls.append(command)
        if command[:3] == ["gh", "run", "list"]:
            return json.dumps([{
                "databaseId": 12345,
                "createdAt": "2099-01-01T00:00:00Z",
            }])
        return ""

    manager._run = fake_run
    manager.trigger_build(wait=True)
    assert [
        "gh", "workflow", "run", "docker-build.yml",
        "--repo", "alice/nihil-images", "--ref", "nihil/web-custom", "-f", "variant=all",
    ] in calls
    assert ["gh", "run", "watch", "12345", "--repo", "alice/nihil-images", "--exit-status"] in calls


def test_personal_source_repoints_docker_image_references():
    from nihil.cli.controller import NihilController

    controller = NihilController.__new__(NihilController)
    controller.config = SimpleNamespace(
        image_source_active="personal",
        personal_image_repo="Alice/nihil-images",
        personal_image_branch="nihil/web-custom",
    )
    controller.manager = SimpleNamespace()
    NihilController._configure_image_registry(controller)

    assert controller.manager.AVAILABLE_IMAGES["web"] == "ghcr.io/alice/web:nihil-web-custom"
    assert controller.manager.DEFAULT_IMAGE == "ghcr.io/alice/full:nihil-web-custom"


def test_personal_source_uses_latest_without_a_custom_branch():
    from nihil.cli.controller import NihilController

    controller = NihilController.__new__(NihilController)
    controller.config = SimpleNamespace(
        image_source_active="personal",
        personal_image_repo="Alice/nihil-images",
    )
    controller.manager = SimpleNamespace()
    NihilController._configure_image_registry(controller)

    assert controller.manager.AVAILABLE_IMAGES["full"] == "ghcr.io/alice/full:latest"


@pytest.mark.parametrize("active", ["upstream", "personal"])
@pytest.mark.parametrize("outcome", ["cancel", "missing_manifest", "push_failure", "save_local", "push"])
def test_customization_only_activates_source_on_success(tmp_path, monkeypatch, active, outcome):
    from copy import deepcopy
    import subprocess
    from unittest.mock import Mock
    from nihil.cli.controller import NihilController
    from nihil.config import NihilConfig

    config = NihilConfig.__new__(NihilConfig)
    config._data = {
        "image_sources": {
            "active": active,
            "home": str(tmp_path),
            "personal_repo": "alice/nihil-images",
            "personal_branch": "nihil/ad-custom",
            "personal_path": str(tmp_path / "previous"),
        },
        "build": {"images_path": str(tmp_path / "previous")},
    }
    config.save = Mock()
    before = deepcopy(config._data)
    source = ImageSourceManager(config)
    # Exercise actual fork preparation and config transitions, without network/Git writes.
    source._run = Mock(return_value="")
    source._gh_user = Mock(return_value="alice")
    source._default_branch = Mock(return_value="main")
    path = tmp_path / "alice" / "nihil-images"
    (path / "build" / "config").mkdir(parents=True)
    if outcome != "missing_manifest":
        (path / "build" / "config" / "tools.json").write_text(
            json.dumps({"core_tools": [{"name": "vim"}], "mod_web": [{"name": "httpx"}]}))
    controller = NihilController.__new__(NihilController)
    controller.formatter = Mock()
    controller.formatter.console = None
    controller._select_tools_tui = Mock(return_value=None if outcome == "cancel" else {"httpx"})
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **kw: True)
    git = Mock()
    if outcome == "push_failure":
        git.side_effect = [None, None, subprocess.CalledProcessError(1, ["git", "push"])]
    monkeypatch.setattr(subprocess, "run", git)
    args = create_parser().parse_args(["image", "customize", "web"] +
                                      (["--no-push"] if outcome == "save_local" else []))

    rc = controller._customize_image(args, source)

    if outcome in {"save_local", "push"}:
        assert rc == 0
        assert config.image_source_active == "personal"
        assert config.personal_image_branch == "nihil/web-custom"
        assert config.personal_image_path == path
        config.save.assert_called_once()
    else:
        assert rc == (0 if outcome == "cancel" else 1)
        assert config._data == before
        config.save.assert_not_called()
