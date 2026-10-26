from types import SimpleNamespace
from unittest.mock import MagicMock

import docker
import pytest

from nihil.exceptions import DockerUnavailable
from nihil.utils.doctor import CheckStatus, DoctorCheckResult, NihilDoctor

IMAGES = {
    "full": "ghcr.io/thenullpigeons/full:latest",
    "ad": "ghcr.io/thenullpigeons/ad:latest",
}


def _manager(installed):
    def get(image):
        if image in installed:
            return MagicMock()
        raise docker.errors.ImageNotFound(image)

    return SimpleNamespace(
        AVAILABLE_IMAGES=IMAGES,
        short_image_name=lambda tag: tag,
        client=SimpleNamespace(images=SimpleNamespace(get=get)),
    )


def _statuses(results):
    return {r.name.split("'")[1]: r.status for r in results}


def test_missing_optional_image_is_a_warning_with_fix():
    results = NihilDoctor(formatter=MagicMock())._check_image(_manager({IMAGES["full"]}))

    assert _statuses(results) == {"full": CheckStatus.OK, "ad": CheckStatus.WARN}
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
