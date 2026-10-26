import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import docker
import pytest

from nihil.cli.parser import create_parser
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
    return {r.name.split()[1].split("/")[-1].split(":")[0]: r.status for r in results}


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
    docker_results = doctor._render.call_args.args[0][1][2]
    assert docker_results == [DoctorCheckResult(
        "Docker daemon accessible", CheckStatus.FAIL, "cannot connect", "start docker",
    )]


def test_plain_render_shows_details_and_fix(capsys):
    formatter = MagicMock()
    formatter.warning.side_effect = lambda text: f"WARN {text}"
    formatter.section_header.side_effect = lambda title: title
    NihilDoctor(formatter=formatter)._render_plain([
        ("Docker", "", [DoctorCheckResult("Image 'ad'", CheckStatus.WARN, "Not installed", "nihil install ad")]),
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


def test_report_masks_identifying_values(doctor, monkeypatch):
    monkeypatch.setattr("nihil.utils.doctor.getpass.getuser", lambda: "alice")
    monkeypatch.setattr("nihil.utils.doctor.socket.gethostname", lambda: "kali-box")
    doctor._sensitive = {}

    def containers(manager):
        doctor._sensitive.update({"acme-prod": "<container-1>", "acme": "<container-2>"})
        return [DoctorCheckResult(
            "VPN sessions", CheckStatus.WARN, "Same config used by: acme-prod, acme", "stop acme",
        )]

    doctor._check_containers = containers
    doctor._check_image = MagicMock(return_value=[
        DoctorCheckResult("Host", CheckStatus.INFO, "alice@kali-box | /home/alice/x"),
    ])

    report = doctor._as_markdown(doctor._collect()[0])

    for leaked in ("alice", "kali-box", "acme"):
        assert leaked not in report
    assert "Same config used by: &lt;container-1&gt;, &lt;container-2&gt;" in report
    assert "&lt;user&gt;@&lt;host&gt; \\| /home/&lt;user&gt;/x" in report


def test_redact_does_not_touch_partial_matches(doctor):
    doctor._sensitive = {"web": "<container-1>"}

    assert doctor._redact("Image 'web' (web:main), webhook") == "Image '<container-1>' (<container-1>:main), webhook"


def test_vpn_and_container_names_are_registered_as_sensitive(nihil_home):
    for name in ("client.ovpn", "acme.ovpn"):
        (nihil_home / "vpn" / name).write_text("client\n")
    doc = NihilDoctor(formatter=MagicMock())
    doc._check_vpn_host()
    doc._check_containers(SimpleNamespace(
        list_containers=lambda all: [_container("acme-prod")],
        is_container_image_current=lambda c: True,
        running_vpn_sessions=lambda: [],
    ))

    assert doc._sensitive == {"acme.ovpn": "<vpn-config-1>", "acme-prod": "<container-1>"}


def test_json_output(doctor, capsys):
    doctor._check_image = MagicMock(return_value=[DoctorCheckResult("Image 'ad'", CheckStatus.WARN, "Not installed", "nihil install ad")])

    assert doctor.run(output="json") == 0

    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 0
    assert data["summary"] == {"OK": 2, "INFO": 1, "WARN": 1, "FAIL": 0}
    assert data["sections"][1]["checks"][-1] == {
        "name": "Image 'ad'", "status": "WARN", "details": "Not installed", "fix": "nihil install ad",
    }
    doctor._render.assert_not_called()


@pytest.mark.parametrize("argv,report,as_json", [
    (["doctor"], None, False),
    (["doctor", "--report"], "", False),
    (["doctor", "--report", "out.md"], "out.md", False),
    (["doctor", "--report", "-"], "-", False),
    (["doctor", "--json"], None, True),
])
def test_doctor_output_flags(argv, report, as_json):
    args = create_parser().parse_args(argv)

    assert (args.report, args.json) == (report, as_json)


def test_doctor_report_and_json_are_exclusive():
    with pytest.raises(SystemExit):
        create_parser().parse_args(["doctor", "--report", "--json"])


def test_report_file_is_written_next_to_the_table(doctor, tmp_path):
    doctor._check_image = MagicMock(return_value=[])
    target = tmp_path / "report.md"

    assert doctor.run(report_file=str(target)) == 0

    doctor._render.assert_called_once()
    assert target.read_text().startswith("### nihil doctor report")
    doctor.formatter.success.assert_called_once()


def test_report_file_defaults_to_a_dated_name(doctor, tmp_path, monkeypatch):
    doctor._check_image = MagicMock(return_value=[])
    monkeypatch.chdir(tmp_path)

    doctor.run(report_file="")

    [report] = tmp_path.glob("nihil-doctor-*.md")
    assert report.read_text().startswith("### nihil doctor report")


def test_unwritable_report_file_fails(doctor, tmp_path):
    doctor._check_image = MagicMock(return_value=[])

    assert doctor.run(report_file=str(tmp_path / "missing-dir" / "report.md")) == 1
    doctor.formatter.error.assert_called_once()


@pytest.mark.parametrize("argv,kwargs", [
    (["doctor"], {"report_file": None}),
    (["doctor", "--report"], {"report_file": ""}),
    (["doctor", "--report", "out.md"], {"report_file": "out.md"}),
    (["doctor", "--report", "-"], {"output": "report"}),
    (["doctor", "--json"], {"output": "json"}),
])
def test_controller_routes_doctor_output(monkeypatch, argv, kwargs):
    from nihil.cli.controller import NihilController

    doctor = MagicMock()
    doctor.run.return_value = 0
    monkeypatch.setattr("nihil.cli.controller.NihilDoctor", lambda formatter: doctor)
    monkeypatch.setattr("nihil.cli.controller.print_compact_banner", MagicMock())
    controller = object.__new__(NihilController)
    controller.parser = create_parser()
    controller.formatter = MagicMock()

    assert controller.run(argv) == 0
    doctor.run.assert_called_once_with(**kwargs)


@pytest.mark.parametrize("columns,fix_column", [("80", False), ("140", True)])
def test_render_keeps_brackets_and_places_fix_by_width(monkeypatch, capsys, columns, fix_column):
    monkeypatch.setenv("COLUMNS", columns)
    NihilDoctor(formatter=MagicMock())._render([
        ("Environment", "cyan", [DoctorCheckResult(
            "Config file", CheckStatus.FAIL, "Unreadable (line 1: [unclosed)", "nihil config --edit",
        )]),
    ])

    out = capsys.readouterr().out
    assert "[unclosed" in out
    assert ("│ Fix" in out) == fix_column
    assert ("→ nihil config --edit" in out) == (not fix_column)
