#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Doctor — diagnostic de l'environnement local."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from typing import List, Optional

import docker

from nihil.exceptions import DockerUnavailable, ImagePullFailed, NihilError
from nihil.console import NihilFormatter
from nihil.manager import NihilManager


@dataclass
class DoctorCheckResult:
    name: str
    ok: bool
    details: Optional[str] = None


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
            docker_results.append(DoctorCheckResult("Docker daemon accessible", True))
            docker_results.extend(self._check_image(manager))
        except NihilError as e:
            docker_results.append(DoctorCheckResult("Docker daemon accessible", False, str(e)))
            exit_code = e.exit_code
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            console = Console()
            env_table = Table(show_header=True, header_style="bold cyan")
            env_table.add_column("Check", style="bold")
            env_table.add_column("Status", style="bold")
            env_table.add_column("Details")
            for r in env_results:
                status = "[green]OK[/]" if r.ok else "[red]FAIL[/]"
                env_table.add_row(r.name, status, r.details or "")
            console.print(Panel(env_table, title="[bold]Environment[/] 🌍", border_style="cyan", padding=(0, 1)))
            docker_table = Table(show_header=True, header_style="bold magenta")
            docker_table.add_column("Check", style="bold")
            docker_table.add_column("Status", style="bold")
            docker_table.add_column("Details")
            for r in docker_results:
                status = "[green]OK[/]" if r.ok else "[red]FAIL[/]"
                docker_table.add_row(r.name, status, r.details or "")
            console.print(Panel(docker_table, title="[bold]Docker[/] 🐋", border_style="magenta", padding=(0, 1)))
        except ImportError:
            print(self.formatter.section_header("Environment", "🌍"))
            for r in env_results:
                prefix = self.formatter.success(r.name) if r.ok else self.formatter.error(r.name)
                print(f"{prefix}\n  {r.details}") if r.details else print(prefix)
            print()
            print(self.formatter.section_header("Docker", "🐋"))
            for r in docker_results:
                prefix = self.formatter.success(r.name) if r.ok else self.formatter.error(r.name)
                print(f"{prefix}\n  {r.details}") if r.details else print(prefix)
        if exit_code is not None:
            return exit_code
        return 0

    def _check_runtime(self) -> List[DoctorCheckResult]:
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return [
            DoctorCheckResult("Python >= 3.12", sys.version_info >= (3, 12), f"Detected Python: {py}"),
            DoctorCheckResult("Detected OS", True, f"{platform.system()} {platform.release()} ({platform.machine()})"),
            DoctorCheckResult("Docker SDK present", True, f"docker=={getattr(docker, '__version__', '?')}"),
            DoctorCheckResult("DOCKER_HOST", True, os.environ.get("DOCKER_HOST", "<not set>")),
        ]

    def _check_image(self, manager: NihilManager) -> List[DoctorCheckResult]:
        out: List[DoctorCheckResult] = []
        unique_images: dict[str, str] = {}
        for label, image in manager.AVAILABLE_IMAGES.items():
            if image == manager.DEFAULT_IMAGE and "full" in manager.AVAILABLE_IMAGES:
                display = f"Image 'full' ({image})"
            else:
                display = f"Image '{label}' ({image})"
            unique_images[image] = display
        for image, display_name in unique_images.items():
            try:
                manager.client.images.get(image)
                out.append(DoctorCheckResult(display_name, True, "Present locally"))
            except docker.errors.ImageNotFound:
                out.append(DoctorCheckResult(display_name, True, "Not present locally"))
            except docker.errors.DockerException as e:
                out.append(DoctorCheckResult(display_name, False, str(e)))
        return out
