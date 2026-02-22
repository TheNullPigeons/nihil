#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Docker Manager for Nihil - Handles Docker images and containers"""

import docker
from typing import Optional, Dict, List
import sys
from pathlib import Path
from nihil.nihilFormatter import NihilFormatter
from nihil.nihilError import (
    DockerUnavailable,
    ImagePullFailed,
    ContainerCreateFailed,
    ContainerStartFailed,
    ContainerStopFailed,
    ContainerRemoveFailed,
    ImageRemoveFailed,
)


class NihilManager:
    """Manages Docker interactions for Nihil"""
    
    DEFAULT_IMAGE = "ghcr.io/thenullpigeons/nihil-images:latest"
    
    # Available images (variant -> full registry tag)
    AVAILABLE_IMAGES = {
        "base": "ghcr.io/thenullpigeons/nihil-images:latest",
        "ad": "ghcr.io/thenullpigeons/nihil-images-ad:latest",
        "active-directory": "ghcr.io/thenullpigeons/nihil-images-ad:latest",
        "web": "ghcr.io/thenullpigeons/nihil-images-web:latest",
        "pwn": "ghcr.io/thenullpigeons/nihil-images-pwn:latest",
    }

    # Reverse map: full registry tag -> compact display name
    SHORT_NAMES: dict = {
        "ghcr.io/thenullpigeons/nihil-images:latest":      "nihil",
        "ghcr.io/thenullpigeons/nihil-images-ad:latest":   "nihil-ad",
        "ghcr.io/thenullpigeons/nihil-images-web:latest":  "nihil-web",
        "ghcr.io/thenullpigeons/nihil-images-pwn:latest":  "nihil-pwn",
    }

    @classmethod
    def short_image_name(cls, full_tag: str) -> str:
        """Return a compact display name for a full registry image tag.

        Examples:
            'ghcr.io/thenullpigeons/nihil-images-web:latest' -> 'nihil-web'
            'unknown/my-image:v1'                            -> 'my-image:v1'
        """
        if full_tag in cls.SHORT_NAMES:
            return cls.SHORT_NAMES[full_tag]
        # Fallback: strip registry host + org prefix, replace 'nihil-images' -> 'nihil'
        name = full_tag.split("/")[-1] if "/" in full_tag else full_tag
        return name.replace("nihil-images", "nihil", 1)

    def __init__(self):
        ensure_filesystem()
        try:
            self.client = docker.from_env()
            self.client.ping()
            self.formatter = NihilFormatter()
        except docker.errors.DockerException as e:
            raise DockerUnavailable(f"Impossible de se connecter à Docker: {e}")
    
    def ensure_image_exists(self, image: str = None) -> bool:
        """Ensure the image exists, pull from ghcr.io if not found"""
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
        """Pull a Docker image and display per-layer download progress."""
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

        # layer_id -> rich task id
        tasks: dict = {}
        # layer_id -> total bytes (filled when progressDetail arrives)
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
                status   = event.get("status", "")
                detail   = event.get("progressDetail") or {}
                current  = detail.get("current", 0)
                total    = detail.get("total", 0)

                # Skip events without a meaningful layer id
                if not layer_id:
                    if status:
                        console.print(f"[dim]{status}[/]")
                    continue

                # Create a progress task the first time we see this layer
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

                # Update total if we now know it
                if total and totals[layer_id] != total:
                    progress.update(task_id, total=total)
                    totals[layer_id] = total

                # Update status label and progress
                progress.update(
                    task_id,
                    status=status,
                    completed=current if current else (totals[layer_id] if status in ("Pull complete", "Already exists") else None),
                )

    def container_exists(self, name: str) -> bool:
        """Check if a container exists"""
        try:
            self.client.containers.get(name)
            return True
        except docker.errors.NotFound:
            return False
    
    def get_container(self, name: str):
        """Get a container by name"""
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
        workspace: Optional[str] = None
    ):
        """Create a new container"""
        if image is None:
            image = self.DEFAULT_IMAGE
        
        # Ensure image exists before creating container
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
        
        # Configure workspace volume
        if volumes is None:
            volumes = {}
        
        if workspace:
            volumes[workspace] = {"bind": "/workspace", "mode": "rw"}
        
        if volumes:
            container_config["volumes"] = volumes
        
        if network_mode:
            container_config["network_mode"] = network_mode
        
        # Mount user resources if available
        user_resources = Path.home() / ".nihil" / "my-resources"
        if user_resources.exists():
            if "volumes" not in container_config:
                container_config["volumes"] = {}
            container_config["volumes"][str(user_resources)] = {
                "bind": "/opt/my-resources",
                "mode": "rw"
            }
        
        try:
            container = self.client.containers.create(**container_config)
            return container
        except docker.errors.APIError as e:
            raise ContainerCreateFailed(name=name, message=f"Erreur création conteneur: {e}")
    
    def start_container(self, container) -> bool:
        """Start a container"""
        try:
            container.start()
            return True
        except docker.errors.APIError as e:
            raise ContainerStartFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur start: {e}")
    
    def stop_container(self, container) -> bool:
        """Stop a container"""
        try:
            container.stop()
            return True
        except docker.errors.APIError as e:
            raise ContainerStopFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur stop: {e}")
    
    def remove_container(self, container, force: bool = False) -> bool:
        """Remove a container"""
        try:
            container.remove(force=force)
            return True
        except docker.errors.APIError as e:
            raise ContainerRemoveFailed(name=getattr(container, "name", "<unknown>"), message=f"Erreur remove: {e}")
    
    def list_containers(self, all: bool = True) -> List:
        """List all nihil containers"""
        try:
            containers = self.client.containers.list(all=all)
            # Filter nihil containers (those using nihil image)
            nihil_containers = []
            for c in containers:
                try:
                    # Check if the container was created with a nihil image
                    # This works even if the image tag was removed
                    config_image = c.attrs.get('Config', {}).get('Image', '')
                    
                    # Check both the current tags and the original image name
                    has_nihil_tag = c.image.tags and any("nihil" in tag for tag in c.image.tags)
                    created_from_nihil = "nihil" in config_image.lower()
                    
                    if has_nihil_tag or created_from_nihil:
                        nihil_containers.append(c)
                except Exception:
                    # Ignore containers with problematic images
                    pass
            return nihil_containers
        except docker.errors.APIError as e:
            print(f"Error retrieving containers: {e}", file=sys.stderr)
            return []
    
    def list_images(self) -> List:
        """List available nihil images"""
        try:
            images = self.client.images.list()
            nihil_images = [img for img in images if img.tags and any("nihil" in tag for tag in img.tags)]
            return nihil_images
        except docker.errors.APIError as e:
            print(f"Error retrieving images: {e}", file=sys.stderr)
            return []
    
    def exec_in_container(self, container, command: str = "zsh"):
        """Execute a command in a container (interactive mode)"""
        import subprocess
        import shlex
        container_id = container.id
        # Split command string into list for correct execution
        cmd_args = shlex.split(command)
        full_command = ["docker", "exec", "-it", container_id] + cmd_args
        subprocess.run(full_command)
    
    def remove_image(self, image: str, force: bool = False) -> bool:
        """Remove a docker image
        
        Args:
            image: Image name or ID to remove
            force: If True, will attempt to remove even if containers are using it
                   (but Docker will still protect running containers)
        
        Returns:
            True if removal successful, False otherwise
        """
        try:
            # Get image object to check if it exists and get its ID
            try:
                img_obj = self.client.images.get(image)
                image_id = img_obj.id
            except docker.errors.ImageNotFound:
                raise ImageRemoveFailed(image=image, message=f"Image '{image}' not found locally.")
            
            # Try to remove the image (Docker will protect containers automatically)
            # We use force=False by default to let Docker handle protection
            self.client.images.remove(image=image_id, force=False, noprune=False)
            return True
            
        except docker.errors.APIError as e:
            if e.response.status_code == 409:
                # Image is being used by a container
                if force:
                    # Even with --force, we explain that containers must be removed first
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
    
def ensure_filesystem():
    """Ensure critical user directories and files exist"""
    base = Path.home() / ".nihil" / "my-resources" / "setup"

    # --- zsh ---
    zsh_path = base / "zsh"
    zsh_path.mkdir(parents=True, exist_ok=True)
    zshrc_path = zsh_path / "zshrc"
    if not zshrc_path.exists():
        zshrc_path.write_text(
            "# Ajoutez ici votre configuration zsh personnalisée\n"
            "# Elle sera chargée automatiquement dans vos containers Nihil\n"
        )
    aliases_path = zsh_path / "aliases"
    if not aliases_path.exists():
        aliases_path.write_text(
            "# Ajoutez ici vos alias personnalisés\n"
            "# Exemple : alias ll='ls -lah'\n"
        )
    history_path = zsh_path / "history"
    if not history_path.exists():
        history_path.write_text(
            "# Ajoutez ici vos commandes à pré-charger dans l'historique zsh\n"
        )

    # --- nvim ---
    nvim_path = base / "nvim"
    nvim_path.mkdir(parents=True, exist_ok=True)
    init_vim = nvim_path / "init.vim"
    if not init_vim.exists():
        init_vim.write_text(
            "\" Ajoutez ici votre configuration Neovim personnalisée\n"
            "\" Elle sera copiée dans ~/.config/nvim/ à l'intérieur du container\n"
        )

    # --- tmux ---
    tmux_path = base / "tmux"
    tmux_path.mkdir(parents=True, exist_ok=True)
    tmux_conf = tmux_path / "tmux.conf"
    if not tmux_conf.exists():
        tmux_conf.write_text(
            "# Ajoutez ici votre configuration tmux personnalisée\n"
            "# Elle sera fusionnée dans ~/.tmux.conf à l'intérieur du container\n"
            "# Exemple :\n"
            "# set -g mouse on\n"
        )

