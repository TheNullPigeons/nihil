#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Doctor - diagnostic checks for local environment."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

import docker

from nihil.nihilError import DockerUnavailable, ImagePullFailed, NihilError
from nihil.nihilFormatter import NihilFormatter
from nihil.nihilManager import NihilManager


@dataclass
class DoctorCheckResult:
    name: str
    ok: bool
    details: Optional[str] = None


class NihilDoctor:
    """Run diagnostics and print a short health report."""

    def __init__(self, formatter: Optional[NihilFormatter] = None):
        self.formatter = formatter or NihilFormatter()

    def run(self) -> int:
        results: List[DoctorCheckResult] = []
        exit_code: Optional[int] = None

        print(self.formatter.section_header("Nihil doctor", "🩺"))
        results.extend(self._check_runtime())

        # Docker checks (may fail hard)
        try:
            manager = NihilManager()
            results.append(DoctorCheckResult("Docker daemon accessible", True))
            results.extend(self._check_image(manager))
        except NihilError as e:
            results.append(DoctorCheckResult("Docker daemon accessible", False, str(e)))
            exit_code = e.exit_code

        # Render summary + decide exit code
        print(self.formatter.section_header("Résultats", "✅"))
        for r in results:
            prefix = self.formatter.success(r.name) if r.ok else self.formatter.error(r.name)
            if r.details and not r.ok:
                print(f"{prefix}\n  {r.details}")
            else:
                print(prefix)

        # If a critical NihilError happened, keep its exit code (useful for scripting).
        if exit_code is not None:
            return exit_code

        # Doctor should return 0 when everything essential is OK.
        return 0

    def _check_runtime(self) -> List[DoctorCheckResult]:
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return [
            DoctorCheckResult("Python >= 3.12", sys.version_info >= (3, 12), f"Python détecté: {py}"),
            DoctorCheckResult(
                "OS détecté",
                True,
                f"{platform.system()} {platform.release()} ({platform.machine()})",
            ),
            DoctorCheckResult("Docker SDK présent", True, f"docker=={getattr(docker, '__version__', '?')}"),
            DoctorCheckResult(
                "DOCKER_HOST",
                True,
                os.environ.get("DOCKER_HOST", "<non défini>"),
            ),
        ]

    def _check_image(self, manager: NihilManager) -> List[DoctorCheckResult]:
        image = manager.DEFAULT_IMAGE
        out: List[DoctorCheckResult] = []

        # Check local presence; if missing, try pulling (non-interactive).
        try:
            manager.client.images.get(image)
            out.append(DoctorCheckResult(f"Image par défaut disponible ({image})", True))
            return out
        except docker.errors.ImageNotFound:
            # Not a failure by itself: we'll try pulling.
            pass
        except docker.errors.DockerException as e:
            out.append(DoctorCheckResult(f"Inspection image ({image})", False, str(e)))
            return out

        try:
            manager.ensure_image_exists(image)
            out.append(
                DoctorCheckResult(
                    f"Image par défaut disponible ({image})",
                    True,
                    "Image absente localement → pull OK",
                )
            )
        except (ImagePullFailed, DockerUnavailable) as e:
            out.append(DoctorCheckResult(f"Image par défaut disponible ({image})", False, str(e)))

        return out


