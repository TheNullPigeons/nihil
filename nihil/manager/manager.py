#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestion Docker : images et conteneurs Nihil."""

import io
import os
import random
import sys
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Set

import docker

from nihil.config import ensure_filesystem, MY_RESOURCES_DIR
from nihil.features.images import (
    DEFAULT_IMAGE,
    AVAILABLE_IMAGES,
    short_image_name as _short_image_name,
)
from nihil.console import NihilFormatter
from nihil.exceptions import (
    DockerUnavailable,
    ImagePullFailed,
    ContainerCreateFailed,
    ContainerStartFailed,
    ContainerStopFailed,
    ContainerRemoveFailed,
    ImageRemoveFailed,
)


class NihilManager:
    DEFAULT_IMAGE = DEFAULT_IMAGE
    AVAILABLE_IMAGES = AVAILABLE_IMAGES

    @classmethod
    def short_image_name(cls, full_tag: str) -> str:
        return _short_image_name(full_tag)

    def __init__(self):
        ensure_filesystem()
        try:
            self.client = docker.from_env()
            self.client.ping()
            self.formatter = NihilFormatter()
        except docker.errors.DockerException as e:
            raise DockerUnavailable(f"Impossible de se connecter à Docker: {e}")

    def ensure_image_exists(self, image: str = None) -> bool:
        if image is None:
            image = self.DEFAULT_IMAGE
        try:
            self.client.images.get(image)
            return True
        except docker.errors.ImageNotFound:
            print(self.formatter.info(f"Image '{image}' not found locally."))
            print(self.formatter.info(f"Pulling '{image}' from registry..."))
            try:
                self._pull_with_progress(image)
                print(self.formatter.success(f"Image '{image}' pulled successfully."))
                return True
            except docker.errors.APIError as e:
                raise ImagePullFailed(image=image, message=f"Failed to pull image '{image}': {e}")

    def _pull_with_progress(self, image: str) -> None:
        from rich.progress import (
            Progress,
            BarColumn,
            DownloadColumn,
            TransferSpeedColumn,
            TimeRemainingColumn,
            TextColumn,
        )
        from rich.console import Console
        console = Console()
        tasks: dict = {}
        totals: dict = {}
        with Progress(
            TextColumn("[bold cyan]{task.fields[layer]:<14}[/]"),
            TextColumn("[bold white]{task.fields[status]:<20}[/]"),
            BarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        ) as progress:
            for event in self.client.api.pull(image, stream=True, decode=True):
                layer_id = event.get("id", "")
                status = event.get("status", "")
                detail = event.get("progressDetail") or {}
                current = detail.get("current", 0)
                total = detail.get("total", 0)
                if not layer_id:
                    if status:
                        console.print(f"[dim]{status}[/]")
                    continue
                if layer_id not in tasks:
                    task_id = progress.add_task(
                        "",
                        layer=layer_id,
                        status=status,
                        total=total or 0,
                        completed=0,
                    )
                    tasks[layer_id] = task_id
                    totals[layer_id] = total
                task_id = tasks[layer_id]
                if total and totals[layer_id] != total:
                    progress.update(task_id, total=total)
                    totals[layer_id] = total
                progress.update(
                    task_id,
                    status=status,
                    completed=current if current else (totals[layer_id] if status in ("Pull complete", "Already exists") else None),
                )

    def container_exists(self, name: str) -> bool:
        try:
            self.client.containers.get(name)
            return True
        except docker.errors.NotFound:
            return False

    def get_container(self, name: str):
        try:
            return self.client.containers.get(name)
        except docker.errors.NotFound:
            return None

    def create_container(
        self,
        name: str,
        image: str = None,
        privileged: bool = False,
        volumes: Optional[Dict] = None,
        network_mode: Optional[str] = None,
        workspace: Optional[str] = None,
        vpn: bool = False,
        vpn_config_path: Optional[str] = None,
        enable_x11: bool = False,
        disable_my_resources: bool = False,
        my_resources_path: Optional[Path] = None,
        browser_ui: bool = False,
        browser_ui_port: Optional[int] = None,
        browser_ui_password: Optional[str] = None,
    ):
        if image is None:
            image = self.DEFAULT_IMAGE
        self.ensure_image_exists(image)
        container_config = {
            "name": name,
            "image": image,
            "detach": True,
            "tty": True,
            "stdin_open": True,
            "privileged": privileged,
            "hostname": name,
        }
        if volumes is None:
            volumes = {}
        if workspace:
            volumes[workspace] = {"bind": "/workspace", "mode": "rw"}
        if enable_x11:
            display = os.environ.get("DISPLAY")
            x11_socket = Path("/tmp/.X11-unix")
            if display and x11_socket.exists():
                volumes[str(x11_socket)] = {"bind": "/tmp/.X11-unix", "mode": "rw"}
        if volumes:
            container_config["volumes"] = volumes
        if network_mode:
            container_config["network_mode"] = network_mode
        if vpn and vpn_config_path:
            vpn_file = Path(vpn_config_path).expanduser().resolve()
            if not vpn_file.is_file():
                raise ContainerCreateFailed(
                    name=name,
                    message=f"VPN config is not a file or does not exist: {vpn_file}",
                )
            if "volumes" not in container_config:
                container_config["volumes"] = {}
            container_config["volumes"][str(vpn_file)] = {"bind": "/opt/nihil/vpn/client.ovpn", "mode": "ro"}
            container_config["environment"] = container_config.get("environment") or {}
            if isinstance(container_config["environment"], list):
                container_config["environment"] = dict(
                    kv.split("=", 1) for kv in container_config["environment"] if "=" in kv
                )
            container_config["environment"]["NIHIL_VPN"] = "1"
        if enable_x11:
            display = os.environ.get("DISPLAY")
            if display:
                container_config["environment"] = container_config.get("environment") or {}
                if isinstance(container_config["environment"], list):
                    container_config["environment"] = dict(
                        kv.split("=", 1) for kv in container_config["environment"] if "=" in kv
                    )
                container_config["environment"]["DISPLAY"] = display
                session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
                wayland_display = os.environ.get("WAYLAND_DISPLAY")
                if session_type == "wayland" or wayland_display:
                    x_mode = "xwayland"
                elif session_type == "x11":
                    x_mode = "x11"
                else:
                    x_mode = "unknown"
                container_config["environment"]["NIHIL_X_MODE"] = x_mode
                xauth = os.environ.get("XAUTHORITY")
                if xauth:
                    xauth_path = Path(xauth).expanduser()
                    if xauth_path.is_file():
                        if "volumes" not in container_config:
                            container_config["volumes"] = {}
                        container_config["volumes"][str(xauth_path)] = {
                            "bind": str(xauth_path),
                            "mode": "ro",
                        }
        effective_my_resources = my_resources_path if my_resources_path is not None else MY_RESOURCES_DIR
        if not disable_my_resources and effective_my_resources.exists():
            if "volumes" not in container_config:
                container_config["volumes"] = {}
            container_config["volumes"][str(effective_my_resources)] = {
                "bind": "/opt/my-resources",
                "mode": "rw"
            }
        if vpn and vpn_config_path:
            container_config["cap_add"] = ["NET_ADMIN"]
            container_config["devices"] = ["/dev/net/tun"]
        if browser_ui:
            if browser_ui_port is None:
                used_ports = self.get_used_browser_ui_ports()
                for lo, hi in [(6901, 7000), (7000, 7100)]:
                    candidates = [p for p in range(lo, hi) if p not in used_ports]
                    if candidates:
                        browser_ui_port = random.choice(candidates)
                        break
                else:
                    browser_ui_port = 6901
            container_config["environment"] = container_config.get("environment") or {}
            if isinstance(container_config["environment"], list):
                container_config["environment"] = dict(
                    kv.split("=", 1) for kv in container_config["environment"] if "=" in kv
                )
            container_config["environment"]["NIHIL_BROWSER_UI"] = "1"
            container_config["environment"]["NIHIL_BROWSER_UI_PORT"] = str(browser_ui_port)
            if browser_ui_password:
                container_config["environment"]["NIHIL_BROWSER_UI_PASSWORD"] = browser_ui_password
            if network_mode not in ("host", "none", "disabled"):
                port_key = f"{browser_ui_port}/tcp"
                host_binding = ("127.0.0.1", browser_ui_port)
                container_config["ports"] = container_config.get("ports") or {}
                container_config["ports"][port_key] = host_binding
        try:
            container = self.client.containers.create(**container_config)
            return container
        except docker.errors.APIError as e:
            raise ContainerCreateFailed(name=name, message=f"Erreur création conteneur: {e}")

    def start_container(self, container) -> bool:
        try:
            container.start()
            return True
        except docker.errors.APIError as e:
            raise ContainerStartFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur start: {e}")

    def stop_container(self, container) -> bool:
        try:
            container.stop()
            return True
        except docker.errors.APIError as e:
            raise ContainerStopFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur stop: {e}")

    def remove_container(self, container, force: bool = False) -> bool:
        try:
            container.remove(force=force)
            return True
        except docker.errors.APIError as e:
            raise ContainerRemoveFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur remove: {e}")

    def get_used_browser_ui_ports(self) -> Set[int]:
        used: Set[int] = set()
        for c in self.list_containers(all=True):
            env_list = c.attrs.get("Config", {}).get("Env") or []
            for kv in env_list:
                if kv.startswith("NIHIL_BROWSER_UI_PORT="):
                    try:
                        used.add(int(kv.split("=", 1)[1]))
                    except ValueError:
                        pass
                    break
        return used

    def list_containers(self, all: bool = True) -> List:
        try:
            containers = self.client.containers.list(all=all)
            nihil_containers = []
            for c in containers:
                try:
                    config_image = c.attrs.get('Config', {}).get('Image', '')
                    has_nihil_tag = c.image.tags and any("nihil" in tag for tag in c.image.tags)
                    created_from_nihil = "nihil" in config_image.lower()
                    if has_nihil_tag or created_from_nihil:
                        nihil_containers.append(c)
                except Exception:
                    pass
            return nihil_containers
        except docker.errors.APIError as e:
            print(f"Error retrieving containers: {e}", file=sys.stderr)
            return []

    def list_images(self) -> List:
        try:
            images = self.client.images.list()
            nihil_images = [img for img in images if img.tags and any("nihil" in tag for tag in img.tags)]
            return nihil_images
        except docker.errors.APIError as e:
            print(f"Error retrieving images: {e}", file=sys.stderr)
            return []

    def get_image_info(self, image_tag: str) -> Optional[Dict]:
        try:
            img = self.client.images.get(image_tag)
            size = img.attrs.get("Size", 0)
            return {"size_bytes": size, "id": img.short_id}
        except docker.errors.ImageNotFound:
            return None

    def container_has_tun(self, container) -> bool:
        try:
            exit_code, _ = container.exec_run("test -c /dev/net/tun")
            return exit_code == 0
        except Exception:
            return False

    def copy_file_into_container(self, container, host_path: str, container_path: str) -> bool:
        try:
            path = Path(host_path).expanduser().resolve()
            if not path.is_file():
                return False
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                tar.add(path, arcname=Path(container_path).name)
            buf.seek(0)
            parent = str(Path(container_path).parent)
            container.put_archive(parent, buf.getvalue())
            return True
        except Exception:
            return False

    def exec_in_container(self, container, command: str = "zsh"):
        import subprocess
        import shlex
        container_id = container.id
        cmd_args = shlex.split(command)
        full_command = ["docker", "exec", "-it", container_id] + cmd_args
        subprocess.run(full_command)

    def remove_image(self, image: str, force: bool = False) -> bool:
        try:
            try:
                img_obj = self.client.images.get(image)
                image_id = img_obj.id
            except docker.errors.ImageNotFound:
                raise ImageRemoveFailed(image=image, message=f"Image '{image}' not found locally.")
            self.client.images.remove(image=image_id, force=False, noprune=False)
            return True
        except docker.errors.APIError as e:
            if e.response.status_code == 409:
                if force:
                    raise ImageRemoveFailed(
                        image=image,
                        message=f"Image '{image}' cannot be deleted because it is currently used by one or more containers. "
                                f"Remove all containers using this image first with 'nihil remove <container_name>'."
                    )
                else:
                    raise ImageRemoveFailed(
                        image=image,
                        message=f"Image '{image}' is currently used by a container. "
                                f"Use --force to see which containers are using it, or remove them first."
                    )
            elif e.response.status_code == 404:
                raise ImageRemoveFailed(image=image, message=f"Image '{image}' not found.")
