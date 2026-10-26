#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Doctor: diagnostic de l'environnement local."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import docker

from nihil.exceptions import NihilError
from nihil.console import NihilFormatter
from nihil.manager import NihilManager
from nihil.utils.platform_info import get_host_os, get_docker_engine, HostOS, DockerEngine


class CheckStatus(Enum):
    OK = "OK"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


_RICH_STYLES = {
    CheckStatus.OK: "green",
    CheckStatus.INFO: "cyan",
    CheckStatus.WARN: "yellow",
    CheckStatus.FAIL: "red",
}


@dataclass
class DoctorCheckResult:
    name: str
    status: CheckStatus
    details: Optional[str] = None
    fix: Optional[str] = None


class NihilDoctor:
    def __init__(self, formatter: Optional[NihilFormatter] = None):
        self.formatter = formatter or NihilFormatter()

    def run(self) -> int:
        exit_code: Optional[int] = None
        print(self.formatter.section_header("Nihil doctor", "🩺"))
        env_results = self._check_runtime()
        docker_results: List[DoctorCheckResult] = []
        try:
            manager = NihilManager()
            docker_results.append(DoctorCheckResult("Docker daemon accessible", CheckStatus.OK))
            docker_results.extend(self._check_docker_engine(manager))
            docker_results.extend(self._check_image(manager))
        except NihilError as e:
            docker_results.append(DoctorCheckResult(
                "Docker daemon accessible", CheckStatus.FAIL, e.message, e.hint,
            ))
            exit_code = e.exit_code
        self._render([
            ("Environment", "🌍", "cyan", env_results),
            ("Docker", "🐋", "magenta", docker_results),
        ])
        if exit_code is not None:
            return exit_code
        if any(r.status == CheckStatus.FAIL for r in env_results + docker_results):
            return 1
        return 0

    def _render(self, sections) -> None:
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
        except ImportError:
            self._render_plain(sections)
            return
        console = Console()
        for title, icon, color, results in sections:
            show_fix = any(r.fix for r in results)
            table = Table(show_header=True, header_style=f"bold {color}")
            table.add_column("Check", style="bold")
            table.add_column("Status", style="bold")
            table.add_column("Details")
            if show_fix:
                table.add_column("Fix")
            for r in results:
                row = [r.name, f"[{_RICH_STYLES[r.status]}]{r.status.value}[/]", r.details or ""]
                if show_fix:
                    row.append(r.fix or "")
                table.add_row(*row)
            console.print(Panel(table, title=f"[bold]{title}[/] {icon}", border_style=color, padding=(0, 1)))

    def _render_plain(self, sections) -> None:
        styles = {
            CheckStatus.OK: self.formatter.success,
            CheckStatus.INFO: self.formatter.info,
            CheckStatus.WARN: self.formatter.warning,
            CheckStatus.FAIL: self.formatter.error,
        }
        for index, (title, icon, _, results) in enumerate(sections):
            if index:
                print()
            print(self.formatter.section_header(title, icon))
            for r in results:
                print(styles[r.status](r.name))
                if r.details:
                    print(f"  {r.details}")
                if r.fix:
                    print(f"  Fix: {r.fix}")

    def _check_runtime(self) -> List[DoctorCheckResult]:
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        host_os = get_host_os()
        python_ok = sys.version_info >= (3, 12)
        results = [
            DoctorCheckResult(
                "Python >= 3.12",
                CheckStatus.OK if python_ok else CheckStatus.FAIL,
                f"Detected Python: {py}",
                None if python_ok else "Install Python 3.12 or newer",
            ),
            DoctorCheckResult("Detected OS", CheckStatus.INFO, f"{platform.system()} {platform.release()} ({platform.machine()})"),
            DoctorCheckResult("Docker SDK", CheckStatus.INFO, f"docker=={getattr(docker, '__version__', '?')}"),
            DoctorCheckResult("DOCKER_HOST", CheckStatus.INFO, os.environ.get("DOCKER_HOST", "<not set>")),
        ]
        if host_os == HostOS.MACOS:
            results.extend(self._check_macos())
        return results

    def _check_macos(self) -> List[DoctorCheckResult]:
        xquartz_path = Path("/Applications/Utilities/XQuartz.app")
        if xquartz_path.exists() or shutil.which("xquartz") is not None:
            return [DoctorCheckResult("XQuartz installed", CheckStatus.OK, "Found")]
        return [DoctorCheckResult(
            "XQuartz installed",
            CheckStatus.WARN,
            "Not found, required only for X11 forwarding",
            "Install it from https://www.xquartz.org",
        )]

    def _check_docker_engine(self, manager: NihilManager) -> List[DoctorCheckResult]:
        host_os = get_host_os()
        engine = get_docker_engine(manager.client)
        engine_labels = {
            DockerEngine.NATIVE: "Native Docker",
            DockerEngine.DOCKER_DESKTOP: "Docker Desktop",
            DockerEngine.ORBSTACK: "OrbStack",
            DockerEngine.UNKNOWN: "Unknown",
        }
        label = engine_labels.get(engine, "Unknown")
        results = [DoctorCheckResult("Docker engine", CheckStatus.INFO, label)]
        if host_os == HostOS.MACOS and engine == DockerEngine.DOCKER_DESKTOP:
            results.append(DoctorCheckResult(
                "Host networking",
                CheckStatus.WARN,
                "Not supported on Docker Desktop",
                "Use OrbStack for full host networking support",
            ))
        return results

    def _check_image(self, manager: NihilManager) -> List[DoctorCheckResult]:
        out: List[DoctorCheckResult] = []
        installed = 0
        seen = set()
        for label, image in manager.AVAILABLE_IMAGES.items():
            if image in seen:
                continue
            seen.add(image)
            display_name = f"Image '{label}' ({manager.short_image_name(image)})"
            try:
                manager.client.images.get(image)
                out.append(DoctorCheckResult(display_name, CheckStatus.OK, "Present locally"))
                installed += 1
            except docker.errors.ImageNotFound:
                out.append(DoctorCheckResult(
                    display_name, CheckStatus.WARN, "Not installed", f"nihil install {label}",
                ))
            except docker.errors.DockerException as e:
                out.append(DoctorCheckResult(display_name, CheckStatus.FAIL, str(e)))
        if not installed:
            # Optional variants only matter once at least one image is usable.
            out = [DoctorCheckResult(r.name, CheckStatus.FAIL, r.details, r.fix)
                   if r.status == CheckStatus.WARN else r for r in out]
        return out
