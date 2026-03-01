#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Browser UI : stockage des mots de passe (wrapper), détection de la page prête."""

import json
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from nihil.config import BROWSER_UI_PASSWORDS_FILE


def save_password(container_name: str, password: str) -> None:
    """Enregistre le mot de passe Browser UI généré par le wrapper (clé = nom du container)."""
    path = BROWSER_UI_PASSWORDS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    data[container_name] = password
    path.write_text(json.dumps(data, indent=0))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_password(container_name: str) -> Optional[str]:
    """Retourne le mot de passe stocké pour le container, ou None."""
    path = BROWSER_UI_PASSWORDS_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get(container_name)
    except (json.JSONDecodeError, OSError):
        return None


def clear_password(container_name: str) -> None:
    """Supprime le mot de passe stocké quand le container est supprimé."""
    path = BROWSER_UI_PASSWORDS_FILE
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        data.pop(container_name, None)
        if data:
            path.write_text(json.dumps(data, indent=0))
        else:
            path.unlink()
    except (json.JSONDecodeError, OSError):
        pass


def get_session_str_for_recap(container, container_name: str) -> Optional[str]:
    """Retourne 'root:password' ou 'root:***' pour le récap; None si inconnu."""
    pwd = load_password(container_name)
    if pwd:
        return f"root:{pwd}"
    env_list = container.attrs.get("Config", {}).get("Env") or []
    if any(e.startswith("NIHIL_BROWSER_UI_PASSWORD=") for e in env_list):
        return "root:***"
    return None


def is_page_ready(port: int) -> bool:
    """True si la page de connexion Browser UI est servie (HTTP 200 + contenu 'Nihil')."""
    try:
        req = Request(f"http://127.0.0.1:{port}/", headers={"User-Agent": "Nihil-Wrapper"})
        with urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                return False
            body = resp.read().decode("utf-8", errors="ignore")
            return "Nihil" in body
    except (URLError, HTTPError, OSError, ValueError):
        return False
