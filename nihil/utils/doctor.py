#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Doctor: diagnostic de l'environnement local."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import docker
import yaml

from nihil.config import CONFIG_FILE, NIHIL_HOME, NihilConfig
from nihil.exceptions import NihilError
from nihil.console import NihilFormatter
from nihil.manager import NihilManager
from nihil.utils.platform_info import get_host_os, get_docker_engine, get_image_platform, HostOS, DockerEngine

# Below this, pulling or updating the full image (~45 GB) is likely to fail.
LOW_DISK_SPACE_GB = 20


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
        env_results = (
            self._check_runtime()
            + self._check_nihil_home()
            + self._check_display()
            + self._check_vpn_host()
        )
        docker_results: List[DoctorCheckResult] = []
        container_results: List[DoctorCheckResult] = []
        try:
            manager = NihilManager()
            docker_results.append(DoctorCheckResult("Docker daemon accessible", CheckStatus.OK))
            docker_results.extend(self._check_docker_engine(manager))
            docker_results.extend(self._check_docker_host(manager))
            docker_results.extend(self._check_image(manager))
            container_results = self._check_containers(manager)
        except NihilError as e:
            docker_results.append(DoctorCheckResult(
                "Docker daemon accessible", CheckStatus.FAIL, e.message, e.hint,
            ))
            exit_code = e.exit_code
        except PermissionError as e:
            # NihilManager creates ~/.nihil subdirectories before talking to Docker.
            docker_results.append(DoctorCheckResult(
                "Docker checks", CheckStatus.FAIL, f"Skipped: {e}", f"sudo chown -R $USER {_tilde(NIHIL_HOME)}",
            ))
        sections = [
            ("Environment", "🌍", "cyan", env_results),
            ("Docker", "🐋", "magenta", docker_results),
        ]
        if container_results:
            sections.append(("Containers", "📦", "green", container_results))
        self._render(sections)
        if exit_code is not None:
            return exit_code
        if any(r.status == CheckStatus.FAIL for _, _, _, results in sections for r in results):
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

    def _check_nihil_home(self) -> List[DoctorCheckResult]:
        results = []
        if not CONFIG_FILE.exists():
            results.append(DoctorCheckResult("Config file", CheckStatus.INFO, "Not created yet, defaults are used"))
        else:
            try:
                data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
                if data is not None and not isinstance(data, dict):
                    raise ValueError("top level must be a mapping")
                results.append(DoctorCheckResult("Config file", CheckStatus.OK, _tilde(CONFIG_FILE)))
            except (yaml.YAMLError, ValueError, OSError) as e:
                mark = getattr(e, "problem_mark", None)
                if mark is not None:
                    reason = f"line {mark.line + 1}: {getattr(e, 'problem', None) or 'invalid YAML'}"
                else:
                    reason = str(e).splitlines()[0]
                results.append(DoctorCheckResult(
                    "Config file",
                    CheckStatus.FAIL,
                    f"Unreadable ({reason}); nihil silently falls back to defaults",
                    "nihil config --edit",
                ))
        # Running nihil once with sudo leaves root-owned directories behind.
        dirs = [NIHIL_HOME] + (sorted(p for p in NIHIL_HOME.iterdir() if p.is_dir()) if NIHIL_HOME.is_dir() else [])
        locked = [_tilde(d) for d in dirs if not os.access(d, os.W_OK | os.X_OK)]
        if locked:
            results.append(DoctorCheckResult(
                "Nihil directory writable",
                CheckStatus.FAIL,
                f"Not writable: {', '.join(locked)}",
                f"sudo chown -R $USER {_tilde(NIHIL_HOME)}",
            ))
        else:
            results.append(DoctorCheckResult("Nihil directory writable", CheckStatus.OK, _tilde(NIHIL_HOME)))
        return results

    def _check_display(self) -> List[DoctorCheckResult]:
        if get_host_os() not in (HostOS.LINUX, HostOS.WSL):
            return []
        config = NihilConfig()
        results = []
        if not config.x11_by_default:
            results.append(DoctorCheckResult("X11 forwarding", CheckStatus.INFO, "Disabled in config"))
        else:
            display = os.environ.get("DISPLAY")
            xauthority = Path(os.environ.get("XAUTHORITY") or Path.home() / ".Xauthority").expanduser()
            if not display:
                results.append(DoctorCheckResult(
                    "X11 forwarding", CheckStatus.WARN, "DISPLAY is not set: GUI apps won't open",
                    "Run nihil from a graphical session",
                ))
            elif not Path("/tmp/.X11-unix").exists():
                results.append(DoctorCheckResult(
                    "X11 forwarding", CheckStatus.WARN, "/tmp/.X11-unix not found: GUI apps won't open",
                    "Check that an X server (or XWayland) is running",
                ))
            elif shutil.which("xhost"):
                results.append(DoctorCheckResult("X11 forwarding", CheckStatus.OK, f"DISPLAY={display}, xhost available"))
            elif xauthority.is_file():
                results.append(DoctorCheckResult("X11 forwarding", CheckStatus.OK, f"DISPLAY={display}, using {_tilde(xauthority)}"))
            else:
                results.append(DoctorCheckResult(
                    "X11 forwarding", CheckStatus.WARN,
                    "Neither xhost nor an Xauthority file found: the X server may refuse GUI apps",
                    "Install xhost (xorg-xhost / x11-xserver-utils)",
                ))
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        if config.wayland_by_default and wayland_display:
            socket = Path(os.environ.get("XDG_RUNTIME_DIR", "")) / wayland_display
            if socket.exists():
                results.append(DoctorCheckResult("Wayland forwarding", CheckStatus.OK, str(socket)))
            else:
                results.append(DoctorCheckResult(
                    "Wayland forwarding", CheckStatus.WARN, f"Socket {socket} not found",
                    "Check XDG_RUNTIME_DIR and WAYLAND_DISPLAY",
                ))
        return results

    def _check_vpn_host(self) -> List[DoctorCheckResult]:
        results = []
        if get_host_os() in (HostOS.LINUX, HostOS.WSL):
            tun = Path("/dev/net/tun")
            if tun.exists() and stat.S_ISCHR(tun.stat().st_mode):
                results.append(DoctorCheckResult("TUN device", CheckStatus.OK, "/dev/net/tun"))
            else:
                results.append(DoctorCheckResult(
                    "TUN device", CheckStatus.WARN, "/dev/net/tun missing: --vpn will fail", "sudo modprobe tun",
                ))
        # Mirrors how `nihil start --vpn` picks a config when no file is given.
        vpn_dir = NIHIL_HOME / "vpn"
        configs = sorted(vpn_dir.glob("*.ovpn")) if vpn_dir.is_dir() else []
        if (vpn_dir / "client.ovpn").is_file():
            results.append(DoctorCheckResult("VPN configs", CheckStatus.OK, f"Default: client.ovpn ({len(configs)} in {_tilde(vpn_dir)})"))
        elif len(configs) == 1:
            results.append(DoctorCheckResult("VPN configs", CheckStatus.OK, f"Default: {configs[0].name}"))
        elif not configs:
            results.append(DoctorCheckResult("VPN configs", CheckStatus.INFO, f"None in {_tilde(vpn_dir)}; pass a file to --vpn"))
        else:
            results.append(DoctorCheckResult(
                "VPN configs",
                CheckStatus.WARN,
                f"{len(configs)} configs and no client.ovpn: --vpn without a file will fail",
                "Name the default one client.ovpn, or use --vpn FILE",
            ))
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

    def _check_docker_host(self, manager: NihilManager) -> List[DoctorCheckResult]:
        try:
            info = manager.client.info()
        except docker.errors.DockerException:
            return []
        results = []
        host_os = get_host_os()
        if any("rootless" in opt for opt in info.get("SecurityOptions") or []):
            results.append(DoctorCheckResult(
                "Rootless Docker", CheckStatus.WARN,
                "--network host uses rootlesskit's namespace, not the real host network",
            ))
        root = info.get("DockerRootDir")
        # Docker Desktop, OrbStack or a remote DOCKER_HOST keep images outside this filesystem.
        if host_os == HostOS.LINUX and root and not os.environ.get("DOCKER_HOST"):
            try:
                free_gb = shutil.disk_usage(root).free / 1024 ** 3
            except OSError:
                free_gb = None
            if free_gb is not None:
                detail = f"{free_gb:.0f} GB free on {root}"
                if free_gb < LOW_DISK_SPACE_GB:
                    results.append(DoctorCheckResult(
                        "Docker disk space", CheckStatus.WARN, f"{detail}; the full image needs about 45 GB",
                        "docker system prune, or nihil uninstall --unused",
                    ))
                else:
                    results.append(DoctorCheckResult("Docker disk space", CheckStatus.OK, detail))
        if get_image_platform():
            if host_os == HostOS.LINUX and get_docker_engine(manager.client) == DockerEngine.NATIVE:
                binfmt = Path("/proc/sys/fs/binfmt_misc")
                handlers = [p.name for p in binfmt.iterdir()] if binfmt.is_dir() else []
                if any(name.startswith("qemu-x86_64") or name == "rosetta" for name in handlers):
                    results.append(DoctorCheckResult("amd64 emulation", CheckStatus.OK, "binfmt handler registered"))
                else:
                    results.append(DoctorCheckResult(
                        "amd64 emulation", CheckStatus.FAIL, "No x86_64 binfmt handler: nihil images won't run",
                        "docker run --privileged --rm tonistiigi/binfmt --install amd64",
                    ))
            else:
                results.append(DoctorCheckResult("amd64 emulation", CheckStatus.INFO, "Provided by the Docker engine"))
        return results

    def _check_image(self, manager: NihilManager) -> List[DoctorCheckResult]:
        out: List[DoctorCheckResult] = []
        installed = 0
        seen = set()
        present = {}
        for label, image in manager.AVAILABLE_IMAGES.items():
            if image in seen:
                continue
            seen.add(image)
            display_name = f"Image '{label}' ({manager.short_image_name(image)})"
            try:
                manager.client.images.get(image)
                out.append(DoctorCheckResult(display_name, CheckStatus.OK, "Present locally"))
                present[len(out) - 1] = (label, image)
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
        if present:
            # Each check is a registry round trip with a 5s timeout: run them together.
            with ThreadPoolExecutor(max_workers=len(present)) as pool:
                updates = dict(zip(present, pool.map(manager.check_image_update, [img for _, img in present.values()])))
            for index, update in updates.items():
                label = present[index][0]
                name = out[index].name
                if update is True:
                    out[index] = DoctorCheckResult(name, CheckStatus.WARN, "Update available", f"nihil update {label}")
                elif update is False:
                    out[index] = DoctorCheckResult(name, CheckStatus.OK, "Up to date")
                else:
                    out[index] = DoctorCheckResult(name, CheckStatus.OK, "Present locally (update check unavailable)")
        return out

    def _check_containers(self, manager: NihilManager) -> List[DoctorCheckResult]:
        containers = manager.list_containers(all=True)
        if not containers:
            return [DoctorCheckResult("Containers", CheckStatus.INFO, "No nihil container yet")]
        running = sum(1 for c in containers if c.status == "running")
        results = [DoctorCheckResult("Containers", CheckStatus.INFO, f"{running} running, {len(containers)} total")]
        outdated = [c.name for c in containers if manager.is_container_image_current(c) is False]
        if outdated:
            results.append(DoctorCheckResult(
                "Container images", CheckStatus.WARN,
                f"Created from an older local image: {', '.join(outdated)}",
                f"nihil upgrade {' '.join(outdated)}",
            ))
        else:
            results.append(DoctorCheckResult("Container images", CheckStatus.OK, "All use their current local image"))
        sessions = manager.running_vpn_sessions()
        by_config = defaultdict(list)
        for name, digest in sessions:
            by_config[digest].append(name)
        shared = [names for names in by_config.values() if len(names) > 1]
        if shared:
            results.append(DoctorCheckResult(
                "VPN sessions", CheckStatus.WARN,
                "Same config used by: " + "; ".join(", ".join(names) for names in shared),
                "Keep one VPN per config: most servers allow one session per identity",
            ))
        elif sessions:
            results.append(DoctorCheckResult("VPN sessions", CheckStatus.OK, f"{len(sessions)} active, no shared config"))
        return results


def _tilde(path: Path) -> str:
    """Display paths under the home directory as ~/... so reports don't leak usernames."""
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home):] if text == home or text.startswith(home + os.sep) else text
