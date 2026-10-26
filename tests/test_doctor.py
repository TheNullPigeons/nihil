from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import docker
import pytest

from nihil.exceptions import DockerUnavailable
from nihil.manager.manager import NihilManager
from nihil.utils.doctor import CheckStatus, DoctorCheckResult, NihilDoctor
from nihil.utils.platform_info import HostOS

IMAGES = {
    "full": "ghcr.io/thenullpigeons/full:latest",
    "ad": "ghcr.io/thenullpigeons/ad:latest",
}


def _manager(installed, updates=None):
    def get(image):
        if image in installed:
            return MagicMock()
        raise docker.errors.ImageNotFound(image)

    return SimpleNamespace(
        AVAILABLE_IMAGES=IMAGES,
        short_image_name=lambda tag: tag,
        check_image_update=lambda tag: (updates or {}).get(tag),
        client=SimpleNamespace(images=SimpleNamespace(get=get)),
    )


def _statuses(results):
    return {r.name.split("'")[1]: r.status for r in results}


def test_missing_optional_image_is_a_warning_with_fix():
    results = NihilDoctor(formatter=MagicMock())._check_image(_manager({IMAGES["full"]}))

    assert _statuses(results) == {"full": CheckStatus.OK, "ad": CheckStatus.WARN}
    assert results[0].details == "Present locally (update check unavailable)"
    assert results[1].fix == "nihil install ad"


def test_no_image_installed_is_a_failure():
    results = NihilDoctor(formatter=MagicMock())._check_image(_manager(set()))

    assert _statuses(results) == {"full": CheckStatus.FAIL, "ad": CheckStatus.FAIL}
    assert results[0].fix == "nihil install full"


def test_duplicate_image_tags_are_checked_once():
    manager = _manager({IMAGES["full"]})
    manager.AVAILABLE_IMAGES = {"full": IMAGES["full"], "default": IMAGES["full"]}

    assert len(NihilDoctor(formatter=MagicMock())._check_image(manager)) == 1


@pytest.fixture
def doctor(monkeypatch):
    doc = NihilDoctor(formatter=MagicMock())
    doc._render = MagicMock()
    doc._check_runtime = MagicMock(return_value=[DoctorCheckResult("Python", CheckStatus.OK)])
    doc._check_docker_engine = MagicMock(return_value=[DoctorCheckResult("Engine", CheckStatus.INFO)])
    for name in ("_check_nihil_home", "_check_display", "_check_vpn_host", "_check_docker_host", "_check_containers"):
        setattr(doc, name, MagicMock(return_value=[]))
    monkeypatch.setattr("nihil.utils.doctor.NihilManager", MagicMock())
    return doc


@pytest.mark.parametrize("status,expected", [
    (CheckStatus.OK, 0),
    (CheckStatus.INFO, 0),
    (CheckStatus.WARN, 0),
    (CheckStatus.FAIL, 1),
])
def test_exit_code_reflects_worst_status(doctor, status, expected):
    doctor._check_image = MagicMock(return_value=[DoctorCheckResult("Image", status)])

    assert doctor.run() == expected


def test_unreachable_daemon_reports_hint_and_error_exit_code(doctor, monkeypatch):
    monkeypatch.setattr(
        "nihil.utils.doctor.NihilManager",
        MagicMock(side_effect=DockerUnavailable("cannot connect", hint="start docker")),
    )

    assert doctor.run() == 2
    docker_results = doctor._render.call_args.args[0][1][3]
    assert docker_results == [DoctorCheckResult(
        "Docker daemon accessible", CheckStatus.FAIL, "cannot connect", "start docker",
    )]


def test_plain_render_shows_details_and_fix(capsys):
    formatter = MagicMock()
    formatter.warning.side_effect = lambda text: f"WARN {text}"
    formatter.section_header.side_effect = lambda title, icon: title
    NihilDoctor(formatter=formatter)._render_plain([
        ("Docker", "", "", [DoctorCheckResult("Image 'ad'", CheckStatus.WARN, "Not installed", "nihil install ad")]),
    ])

    assert capsys.readouterr().out.splitlines() == [
        "Docker", "WARN Image 'ad'", "  Not installed", "  Fix: nihil install ad",
    ]


@pytest.mark.parametrize("update,status,details,fix", [
    (True, CheckStatus.WARN, "Update available", "nihil update full"),
    (False, CheckStatus.OK, "Up to date", None),
])
def test_installed_image_reports_update_state(update, status, details, fix):
    manager = _manager({IMAGES["full"]}, updates={IMAGES["full"]: update})

    result = NihilDoctor(formatter=MagicMock())._check_image(manager)[0]

    assert (result.status, result.details, result.fix) == (status, details, fix)


def test_failure_in_any_section_sets_exit_code(doctor):
    doctor._check_image = MagicMock(return_value=[])
    doctor._check_containers = MagicMock(return_value=[DoctorCheckResult("VPN", CheckStatus.FAIL)])

    assert doctor.run() == 1
    assert doctor._render.call_args.args[0][2][0] == "Containers"


@pytest.fixture
def nihil_home(tmp_path, monkeypatch):
    home = tmp_path / ".nihil"
    (home / "vpn").mkdir(parents=True)
    monkeypatch.setattr("nihil.utils.doctor.NIHIL_HOME", home)
    monkeypatch.setattr("nihil.utils.doctor.CONFIG_FILE", home / "config.yml")
    monkeypatch.setattr("nihil.utils.doctor.get_host_os", lambda: HostOS.LINUX)
    return home


def _by_name(results, name):
    return next(r for r in results if r.name == name)


@pytest.mark.parametrize("content,status", [
    (None, CheckStatus.INFO),
    ("network:\n  default_network: docker\n", CheckStatus.OK),
    ("network: [unclosed\n", CheckStatus.FAIL),
    ("- just\n- a list\n", CheckStatus.FAIL),
])
def test_config_file_check(nihil_home, content, status):
    if content is not None:
        (nihil_home / "config.yml").write_text(content)

    result = _by_name(NihilDoctor(formatter=MagicMock())._check_nihil_home(), "Config file")

    assert result.status == status
    if status == CheckStatus.FAIL:
        assert result.fix == "nihil config --edit"


def test_unwritable_nihil_directory_fails(nihil_home, monkeypatch):
    locked = nihil_home / "vpn"
    monkeypatch.setattr("nihil.utils.doctor.os.access", lambda path, mode: Path(path) != locked)

    result = _by_name(NihilDoctor(formatter=MagicMock())._check_nihil_home(), "Nihil directory writable")

    assert result.status == CheckStatus.FAIL
    assert result.details == f"Not writable: {locked}"


@pytest.mark.parametrize("files,status", [
    ([], CheckStatus.INFO),
    (["htb.ovpn"], CheckStatus.OK),
    (["htb.ovpn", "client.ovpn"], CheckStatus.OK),
    (["htb.ovpn", "thm.ovpn"], CheckStatus.WARN),
])
def test_vpn_config_resolution(nihil_home, files, status):
    for name in files:
        (nihil_home / "vpn" / name).write_text("client\n")

    result = _by_name(NihilDoctor(formatter=MagicMock())._check_vpn_host(), "VPN configs")

    assert result.status == status


@pytest.mark.parametrize("env,status", [
    ({}, CheckStatus.WARN),
    ({"DISPLAY": ":0"}, CheckStatus.OK),
])
def test_x11_check_needs_display(nihil_home, monkeypatch, env, status):
    for var in ("DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "nihil.utils.doctor.NihilConfig",
        lambda: SimpleNamespace(x11_by_default=True, wayland_by_default=True),
    )
    monkeypatch.setattr("nihil.utils.doctor.Path.exists", lambda self: True)
    monkeypatch.setattr("nihil.utils.doctor.shutil.which", lambda name: "/usr/bin/xhost")

    result = _by_name(NihilDoctor(formatter=MagicMock())._check_display(), "X11 forwarding")

    assert result.status == status


def _container(name, status="running"):
    return SimpleNamespace(name=name, status=status)


def test_containers_report_outdated_images_and_shared_vpn():
    manager = SimpleNamespace(
        list_containers=lambda all: [_container("a"), _container("b"), _container("c", "exited")],
        is_container_image_current=lambda c: c.name != "c",
        running_vpn_sessions=lambda: [("a", "h1"), ("b", "h1")],
    )

    results = NihilDoctor(formatter=MagicMock())._check_containers(manager)

    assert _by_name(results, "Containers").details == "2 running, 3 total"
    images = _by_name(results, "Container images")
    assert (images.status, images.fix) == (CheckStatus.WARN, "nihil upgrade c")
    vpn = _by_name(results, "VPN sessions")
    assert vpn.status == CheckStatus.WARN
    assert "a, b" in vpn.details


def test_containers_without_issues():
    manager = SimpleNamespace(
        list_containers=lambda all: [_container("a"), _container("b")],
        is_container_image_current=lambda c: None if c.name == "b" else True,
        running_vpn_sessions=lambda: [("a", "h1"), ("b", "h2")],
    )

    results = NihilDoctor(formatter=MagicMock())._check_containers(manager)

    assert {r.name: r.status for r in results} == {
        "Containers": CheckStatus.INFO,
        "Container images": CheckStatus.OK,
        "VPN sessions": CheckStatus.OK,
    }


def test_running_vpn_sessions_skips_containers_without_tun_or_vpn():
    manager = object.__new__(NihilManager)
    tun = {"HostConfig": {"Devices": [{"PathOnHost": "/dev/net/tun"}]}}
    containers = [
        SimpleNamespace(id="1", name="vpn", attrs=tun),
        SimpleNamespace(id="2", name="no-vpn", attrs=tun),
        SimpleNamespace(id="3", name="no-tun", attrs={"HostConfig": {}}),
    ]
    manager.list_containers = lambda all: containers
    manager._running_vpn_config = lambda c: "/opt/nihil/vpn/client.ovpn" if c.name == "vpn" else None
    manager._container_file_digest = lambda c, path: "h1"

    assert manager.running_vpn_sessions() == [("vpn", "h1")]
