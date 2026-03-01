# Exceptions métier (Docker, images, conteneurs)
from nihil.exceptions.errors import (
    NihilError,
    DockerUnavailable,
    ImageNotFound,
    ImagePullFailed,
    ContainerNotFound,
    ContainerNotRunning,
    ContainerCreateFailed,
    ContainerStartFailed,
    ContainerStopFailed,
    ContainerRemoveFailed,
    ImageRemoveFailed,
)

__all__ = [
    "NihilError",
    "DockerUnavailable",
    "ImageNotFound",
    "ImagePullFailed",
    "ContainerNotFound",
    "ContainerNotRunning",
    "ContainerCreateFailed",
    "ContainerStartFailed",
    "ContainerStopFailed",
    "ContainerRemoveFailed",
    "ImageRemoveFailed",
]
