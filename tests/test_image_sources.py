from pathlib import Path
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
    assert saved["active"] == "personal"
    assert ["gh", "repo", "fork", "TheNullPigeons/nihil-images", "--clone=false"] not in calls
    assert ["git", "switch", "-c", "nihil/web-custom", "upstream/main"] in calls


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
            return "12345"
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
