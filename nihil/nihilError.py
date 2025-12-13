#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Errors - Domain exceptions and exit codes.

This module centralizes Nihil-specific exceptions so the rest of the codebase
can raise meaningful errors without calling sys.exit() deep in the stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class NihilError(Exception):
    """Base class for all Nihil domain errors."""

    message: str
    exit_code: int = 1
    hint: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover
        if self.hint:
            return f"{self.message}\nHint: {self.hint}"
        return self.message


class DockerUnavailable(NihilError):
    """Raised when Nihil can't talk to the Docker daemon."""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(
            message=message,
            exit_code=2,
            hint=hint
            or "Vérifie que Docker tourne et que ton utilisateur a accès au socket Docker.",
        )


class ImageNotFound(NihilError):
    """Raised when an image is missing locally and cannot be pulled."""

    def __init__(self, image: str, message: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(
            message=message or f"Image introuvable: '{image}'",
            exit_code=3,
            hint=hint or "Essaie `nihil info` ou vérifie ta connexion au registry.",
        )
        self.image = image


class ImagePullFailed(NihilError):
    """Raised when pulling an image fails."""

    def __init__(self, image: str, message: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(
            message=message or f"Impossible de pull l'image: '{image}'",
            exit_code=3,
            hint=hint or "Vérifie l'accès au registry (auth, réseau) et le nom d'image.",
        )
        self.image = image


class ContainerNotFound(NihilError):
    """Raised when a container does not exist."""

    def __init__(self, name: str, message: Optional[str] = None):
        super().__init__(message=message or f"Conteneur introuvable: '{name}'", exit_code=4)
        self.name = name


class ContainerNotRunning(NihilError):
    """Raised when a container exists but is not running."""

    def __init__(self, name: str, message: Optional[str] = None):
        super().__init__(message=message or f"Le conteneur '{name}' n'est pas en cours d'exécution.", exit_code=5)
        self.name = name


class ContainerCreateFailed(NihilError):
    """Raised when container creation fails."""

    def __init__(self, name: str, message: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(
            message=message or f"Échec de création du conteneur: '{name}'",
            exit_code=6,
            hint=hint,
        )
        self.name = name


class ContainerStartFailed(NihilError):
    """Raised when container start fails."""

    def __init__(self, name: str, message: Optional[str] = None):
        super().__init__(message=message or f"Échec du démarrage du conteneur: '{name}'", exit_code=7)
        self.name = name


class ContainerStopFailed(NihilError):
    """Raised when container stop fails."""

    def __init__(self, name: str, message: Optional[str] = None):
        super().__init__(message=message or f"Échec de l'arrêt du conteneur: '{name}'", exit_code=8)
        self.name = name


class ContainerRemoveFailed(NihilError):
    """Raised when container removal fails."""

    def __init__(self, name: str, message: Optional[str] = None):
        super().__init__(message=message or f"Échec de suppression du conteneur: '{name}'", exit_code=9)
        self.name = name


