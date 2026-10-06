from pathlib import Path
import json
import threading
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from nihil.cli.parser import create_parser
from nihil.features.image_sources import ImageSourceError, ImageSourceManager


def test_image_commands_are_available():
    parser = create_parser()

    customize = parser.parse_args(["image", "customize", "web", "--no-push"])
    assert customize.command == "image"
    assert customize.image_action == "customize"
    assert customize.variant == "web"
    assert customize.no_push is True
    assert customize.repo is None
    assert customize.git_protocol == "auto"
    assert customize.git_del is False

    browser = parser.parse_args(["image", "customize", "full", "--web"])
    assert browser.web is True

    https = parser.parse_args(["image", "customize", "web", "--git-protocol", "https"])
    assert https.git_protocol == "https"

    delete = parser.parse_args(["image", "customize", "web", "--git-del"])
    assert delete.git_del == "local"

    for mode in ("local", "distant", "all"):
        parsed = parser.parse_args(["image", "customize", "web", "--git-del", mode])
        assert parsed.git_del == mode

    switch = parser.parse_args(["image", "switch", "personal"])
    assert switch.image_action == "switch"
    assert switch.source == "personal"

    channel = parser.parse_args(["image", "channel", "dev"])
    assert channel.image_action == "channel"
    assert channel.channel == "dev"

    build = parser.parse_args(["image", "build", "web", "--wait"])
    assert build.image_action == "build"
    assert build.variant == "web"
    assert build.wait is True


def test_repository_urls_are_normalized(tmp_path):
    config = SimpleNamespace(image_sources_home=tmp_path)
    manager = ImageSourceManager(config, upstream_repo="https://github.com/acme/security-images.git")
    assert manager.upstream_repo == "acme/security-images"


def test_auto_protocol_reads_github_host_configuration(tmp_path):
    config = SimpleNamespace(image_sources_home=tmp_path)
    manager = ImageSourceManager(config)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:4] == ["gh", "config", "get", "git_protocol"]:
            return "ssh"
        return ""

    manager._run = fake_run
    manager._has_ssh_key = staticmethod(lambda: True)
    assert manager._default_git_protocol() == "ssh"
    assert ["gh", "config", "get", "git_protocol", "--host", "github.com"] in calls


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

    def fake_run(command, *, cwd=None, capture=True, timeout=None):
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
    assert ["git", "merge", "--no-edit", "upstream/main"] in calls


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

    def fake_run(command, *, cwd=None, capture=True, timeout=None):
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


def test_distant_cleanup_deletes_branch_and_all_variant_packages(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        image_sources_upstream_path=tmp_path / "upstream" / "nihil-images",
    )
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
            return "origin/main"
        if command[:2] == ["git", "branch"]:
            return "main"
        if command[:4] == ["gh", "repo", "view", "TheNullPigeons/nihil-images"]:
            return "main"
        if command[:3] == ["gh", "api", "--method"] and "DELETE" in command:
            raise ImageSourceError("Command failed: 404 Not Found")
        return ""

    from nihil.features.image_sources import ImageSourceError
    manager._run = fake_run
    manager.ensure_personal_fork(variant="web", delete_existing="distant")

    assert [
        "gh", "api", "--method", "DELETE",
        "repos/alice/nihil-images/git/refs/heads/nihil/web-custom",
    ] in calls
    for package in ("full", "ad", "web", "blueteam"):
        assert [
            "gh", "api", "--method", "DELETE",
            f"users/alice/packages/container/{package}",
        ] in calls


def test_distant_cleanup_suggests_refreshing_package_scopes(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        image_sources_upstream_path=tmp_path / "upstream" / "nihil-images",
    )
    manager = ImageSourceManager(config)
    def fail_package_delete(command, **kwargs):
        if "packages/container" in command[-1]:
            raise ImageSourceError("Command failed: gh api: need delete:packages and read:packages scopes")
        return ""
    manager._run = fail_package_delete
    with pytest.raises(ImageSourceError, match="gh auth refresh -h github.com -s read:packages,delete:packages"):
        manager._delete_remote_customization("alice/nihil-images", "nihil/web-custom")


def test_distant_cleanup_ignores_missing_branch(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        image_sources_upstream_path=tmp_path / "upstream" / "nihil-images",
    )
    manager = ImageSourceManager(config)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "git/refs/heads" in command[-1]:
            raise ImageSourceError("Command failed: Reference does not exist (HTTP 422)")
        return ""

    manager._run = fake_run
    manager._delete_remote_customization("alice/nihil-images", "nihil/web-custom")
    assert sum("packages/container" in command[-1] for command in calls) == 4


def test_trigger_build_dispatches_and_can_wait(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        personal_image_repo="alice/nihil-images",
        personal_image_branch="nihil/web-custom",
    )
    manager = ImageSourceManager(config)
    calls = []

    def fake_run(command, *, cwd=None, capture=True, timeout=None):
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


def test_workflow_progress_tracks_github_steps():
    from nihil.features.image_sources import _workflow_progress

    run = {
        "status": "in_progress",
        "jobs": [{"status": "in_progress", "name": "build-web", "steps": [
            {"name": "Checkout", "status": "completed"},
            {"name": "Build image", "status": "in_progress"},
            {"name": "Push image", "status": "queued"},
        ]}],
    }
    assert _workflow_progress(run) == (1, 3, "Build image")


def test_trigger_build_reports_progress_to_web_ui(tmp_path):
    config = SimpleNamespace(
        image_sources_home=tmp_path,
        personal_image_repo="alice/nihil-images",
        personal_image_branch="nihil/web-custom",
    )
    manager = ImageSourceManager(config)
    updates = []

    def fake_run(command, **kwargs):
        if command[:3] == ["gh", "run", "list"]:
            return json.dumps([{"databaseId": 42, "createdAt": "2099-01-01T00:00:00Z"}])
        if command[:3] == ["gh", "run", "view"]:
            if "--log" in command:
                return "complete build log"
            return json.dumps({
                "status": "completed", "conclusion": "success", "url": "https://github.test/run/42",
                "jobs": [{"status": "completed", "steps": [{"name": "Build", "status": "completed"}]}],
            })
        return ""

    manager._run = fake_run
    manager.trigger_build(wait=True, progress_callback=lambda *update: updates.append(update))
    assert updates[-1] == (1, 1, "Build logs ready", "https://github.test/run/42", "complete build log")


def test_completed_build_retries_until_logs_are_available(tmp_path, monkeypatch):
    manager = ImageSourceManager(SimpleNamespace(image_sources_home=tmp_path))
    logs = iter(["", "complete build log"])
    updates = []

    def fake_run(command, **kwargs):
        if "--log" in command:
            return next(logs)
        return json.dumps({"status": "completed", "conclusion": "success", "jobs": []})

    manager._run = fake_run
    monkeypatch.setattr("nihil.features.image_sources.time.sleep", lambda _: None)
    manager._watch_build("42", "alice/nihil-images", lambda *update: updates.append(update))
    assert updates[-1][-1] == "complete build log"


def test_web_build_can_be_cancelled(tmp_path, monkeypatch):
    from nihil.features.image_sources import BuildCancelled

    manager = ImageSourceManager(SimpleNamespace(image_sources_home=tmp_path))
    calls = []
    runs = iter([
        {"status": "in_progress", "conclusion": "", "url": "https://github.test/run/42", "jobs": []},
        {"status": "completed", "conclusion": "cancelled", "url": "https://github.test/run/42", "jobs": []},
    ])

    def fake_run(command, **kwargs):
        calls.append(command)
        if "--log" in command:
            return "cancelled build log"
        return json.dumps(next(runs)) if command[:3] == ["gh", "run", "view"] else ""

    manager._run = fake_run
    monkeypatch.setattr("nihil.features.image_sources.time.sleep", lambda _: None)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(BuildCancelled):
        manager._watch_build("42", "alice/nihil-images", lambda *args: None, cancelled)
    assert ["gh", "run", "cancel", "42", "--repo", "alice/nihil-images"] in calls


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


def test_upstream_channel_selects_dev_without_changing_personal_images():
    from nihil.cli.controller import NihilController
    from nihil.config.user_config import NihilConfig

    config = NihilConfig.__new__(NihilConfig)
    config._data = {"image_sources": {"active": "upstream", "channel": "dev"}}
    controller = NihilController.__new__(NihilController)
    controller.config = config
    controller.manager = SimpleNamespace()
    controller._configure_image_registry()
    assert controller.manager.AVAILABLE_IMAGES["full"] == "ghcr.io/thenullpigeons/full:dev"
    assert controller.manager.DEFAULT_IMAGE == "ghcr.io/thenullpigeons/full:dev"

    config._data["image_sources"]["active"] = "personal"
    config._data["image_sources"]["personal_repo"] = "Alice/nihil-images"
    config._data["image_sources"]["personal_branch"] = "nihil/web-custom"
    controller._configure_image_registry()
    assert controller.manager.AVAILABLE_IMAGES["web"] == "ghcr.io/alice/web:nihil-web-custom"


def test_update_pulls_dev_after_switching_from_an_installed_main_image():
    from nihil.cli.controller import NihilController

    controller = NihilController.__new__(NihilController)
    controller.formatter = MagicMock()
    image = SimpleNamespace(tags=["ghcr.io/thenullpigeons/full:latest"])
    dev_image = SimpleNamespace(short_id="sha256:1234")
    docker_images = MagicMock()
    docker_images.get.side_effect = [LookupError("dev not installed"), dev_image]
    controller.manager = SimpleNamespace(
        AVAILABLE_IMAGES={"full": "ghcr.io/thenullpigeons/full:dev"},
        list_images=lambda: [image],
        _variant_for_image_tag=lambda tag: "full",
        image_source=lambda tag: "upstream",
        client=SimpleNamespace(images=docker_images),
        _pull_with_progress=MagicMock(),
        get_image_version=lambda img: "dev",
        get_image_display_version=lambda img: "dev @1234",
    )

    assert controller._cmd_update(SimpleNamespace(image=None)) == 0
    controller.manager._pull_with_progress.assert_called_once_with("ghcr.io/thenullpigeons/full:dev")


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


def test_web_customization_pushes_and_builds_without_terminal_confirmation(tmp_path, monkeypatch):
    import subprocess
    from unittest.mock import Mock
    from nihil.cli.controller import NihilController

    path = tmp_path / "nihil-images"
    (path / "build" / "config").mkdir(parents=True)
    (path / "build" / "config" / "tools.json").write_text(json.dumps({
        "core_tools": [{"name": "vim"}], "mod_web": [{"name": "httpx"}],
    }))
    source = Mock()
    source.ensure_personal_fork.return_value = (path, "alice/nihil-images", "nihil/web-custom")
    source.trigger_build.side_effect = lambda **kwargs: kwargs["progress_callback"](
        1, 1, "Build finished", "https://github.test/run/42",
    )
    controller = NihilController.__new__(NihilController)
    controller.formatter = Mock(console=None)

    def select_web(tools, disabled, **kwargs):
        kwargs["on_save"]({"httpx"}, lambda *args: None, threading.Event())
        assert kwargs["action_label"] == "Apply & build"
        assert kwargs["can_cancel"] is True
        return {"httpx"}

    controller._select_tools_web = select_web
    monkeypatch.setattr("rich.prompt.Confirm.ask", Mock(side_effect=AssertionError("unexpected prompt")))
    git = Mock()
    monkeypatch.setattr(subprocess, "run", git)

    args = create_parser().parse_args(["image", "customize", "web", "--web"])
    assert controller._customize_image(args, source) == 0
    source.activate_personal.assert_called_once_with(path, "alice/nihil-images", "nihil/web-custom")
    source.trigger_build.assert_called_once()
    assert git.call_count == 3
