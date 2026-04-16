#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestion du fichier de configuration utilisateur ~/.nihil/config.yml."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from nihil.config.defaults import NIHIL_HOME

CONFIG_FILE = NIHIL_HOME / "config.yml"

_DEFAULT_CONFIG: dict = {
    "network": {
        "default_network": "host",  # host | docker | nat | disabled
    },
    "workspace": {
        "default_path": None,  # None = pas de workspace par défaut
    },
    "shell": {
        "default_shell": "zsh",  # zsh | bash | tmux
        "logging": {
            "always_enable": False,
            "method": "asciinema",  # asciinema | script
        },
    },
    "my_resources": {
        "enabled": True,
        "path": str(NIHIL_HOME / "my-resources"),
    },
    "display": {
        "x11_by_default": True,
    },
    "updates": {
        "auto_check": True,
    },
}

_CONFIG_COMMENT = """\
# Nihil configuration file
# Generated automatically — edit to customize your defaults.
#
# network.default_network     : host | docker | nat | disabled
# workspace.default_path      : absolute path used as default workspace (null = disabled)
# shell.default_shell         : zsh | bash | tmux
# shell.logging.always_enable : always record shell sessions with asciinema
# shell.logging.method        : asciinema | script
# my_resources.enabled        : mount ~/.nihil/my-resources in every container
# my_resources.path           : custom path for my-resources
# display.x11_by_default      : enable X11 forwarding by default
# updates.auto_check          : check for image updates on start

"""


class NihilConfig:
    """Lit et expose la configuration utilisateur depuis ~/.nihil/config.yml."""

    def __init__(self) -> None:
        self._data = self._load()

    # ------------------------------------------------------------------
    # Chargement / sauvegarde
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if not CONFIG_FILE.exists():
            self._write_defaults()
            return _deep_copy(_DEFAULT_CONFIG)
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            data = {}
        return _deep_merge(_DEFAULT_CONFIG, data)

    def _write_defaults(self) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as fh:
            fh.write(_CONFIG_COMMENT)
            yaml.dump(_DEFAULT_CONFIG, fh, default_flow_style=False, allow_unicode=True)

    def save(self) -> None:
        """Persiste la configuration courante sur disque."""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as fh:
            fh.write(_CONFIG_COMMENT)
            yaml.dump(self._data, fh, default_flow_style=False, allow_unicode=True)

    # ------------------------------------------------------------------
    # Propriétés — network
    # ------------------------------------------------------------------

    @property
    def default_network(self) -> str:
        val = self._get("network", "default_network") or "host"
        if val not in ("host", "docker", "nat", "disabled"):
            return "host"
        return val

    # ------------------------------------------------------------------
    # Propriétés — workspace
    # ------------------------------------------------------------------

    @property
    def default_workspace(self) -> Optional[Path]:
        raw = self._get("workspace", "default_path")
        if raw:
            return Path(raw).expanduser().resolve()
        return None

    # ------------------------------------------------------------------
    # Propriétés — shell
    # ------------------------------------------------------------------

    @property
    def default_shell(self) -> str:
        val = self._get("shell", "default_shell") or "zsh"
        if val not in ("zsh", "bash", "tmux"):
            return "zsh"
        return val

    @property
    def logging_always_enable(self) -> bool:
        return bool(self._get("shell", "logging", "always_enable"))

    @property
    def logging_method(self) -> str:
        val = self._get("shell", "logging", "method") or "asciinema"
        if val not in ("asciinema", "script"):
            return "asciinema"
        return val

    # ------------------------------------------------------------------
    # Propriétés — my_resources
    # ------------------------------------------------------------------

    @property
    def my_resources_enabled(self) -> bool:
        val = self._get("my_resources", "enabled")
        return val if val is not None else True

    @property
    def my_resources_path(self) -> Path:
        raw = self._get("my_resources", "path")
        if raw:
            return Path(raw).expanduser().resolve()
        return NIHIL_HOME / "my-resources"

    # ------------------------------------------------------------------
    # Propriétés — display
    # ------------------------------------------------------------------

    @property
    def x11_by_default(self) -> bool:
        return bool(self._get("display", "x11_by_default"))

    # ------------------------------------------------------------------
    # Propriétés — updates
    # ------------------------------------------------------------------

    @property
    def auto_check_updates(self) -> bool:
        val = self._get("updates", "auto_check")
        return val if val is not None else True

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _get(self, *keys: str):
        node = self._data
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node


# ------------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------------

def _deep_copy(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


def _deep_merge(base: dict, override: dict) -> dict:
    """Fusionne override dans base récursivement. base fournit les valeurs par défaut."""
    result = _deep_copy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
