#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Détection de l'OS hôte et du moteur Docker."""

import platform
from enum import Enum


class HostOS(Enum):
    LINUX = "linux"
    MACOS = "macos"
    WSL = "wsl"
    WINDOWS = "windows"


class DockerEngine(Enum):
    NATIVE = "native"
    DOCKER_DESKTOP = "docker_desktop"
    ORBSTACK = "orbstack"
    UNKNOWN = "unknown"


def get_host_os() -> HostOS:
    system = platform.system()
    if system == "Darwin":
        return HostOS.MACOS
    if system == "Windows":
        return HostOS.WINDOWS
    if system == "Linux":
        if "microsoft" in platform.release().lower():
            return HostOS.WSL
        return HostOS.LINUX
    return HostOS.LINUX


def get_docker_engine(docker_client) -> DockerEngine:
    try:
        info = docker_client.info()
        kernel = info.get("KernelVersion", "").lower()
        operating_system = info.get("OperatingSystem", "").lower()
        if "orbstack" in kernel or "orbstack" in operating_system:
            return DockerEngine.ORBSTACK
        if "linuxkit" in kernel or "docker desktop" in operating_system:
            return DockerEngine.DOCKER_DESKTOP
        return DockerEngine.NATIVE
    except Exception:
        return DockerEngine.UNKNOWN


def host_network_supported(host_os: HostOS, engine: DockerEngine) -> bool:
    if host_os == HostOS.LINUX:
        return True
    if host_os == HostOS.WSL and engine == DockerEngine.NATIVE:
        return True
    return False
