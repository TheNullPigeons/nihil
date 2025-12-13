#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Docker Manager for Nihil - Handles Docker images and containers"""

import docker
from typing import Optional, Dict, List
import sys
from nihil.nihilFormatter import NihilFormatter
from nihil.nihilError import (
    DockerUnavailable,
    ImagePullFailed,
    ContainerCreateFailed,
    ContainerStartFailed,
    ContainerStopFailed,
    ContainerRemoveFailed,
)


class NihilManager:
    """Manages Docker interactions for Nihil"""
    
    DEFAULT_IMAGE = "ghcr.io/thenullpigeons/nihil-images:latest"
    
    def __init__(self):
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
                self.client.images.pull(image)
                print(self.formatter.success(f"Image '{image}' pulled successfully."))
                return True
            except docker.errors.APIError as e:
                raise ImagePullFailed(image=image, message=f"Échec du pull de l'image '{image}': {e}")
    
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
                    if c.image.tags and any("nihil" in tag for tag in c.image.tags):
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
    
    def exec_in_container(self, container, command: str = "bash"):
        """Execute a command in a container (interactive mode)"""
        import subprocess
        container_id = container.id
        subprocess.run(["docker", "exec", "-it", container_id, command])
