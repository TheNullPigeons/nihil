#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command history logger for Nihil."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List


# Simple fichier texte, facile à lire et à copier/coller.
# Exemple de ligne :
# 2026-01-23T20:15:03Z exit=0 nihil start my-pentest --privileged
HISTORY_PATH = Path.home() / ".config" / "nihil" / "history.log"


def log_command(argv: List[str], exit_code: int) -> None:
    """Ajoute une entrée lisible dans l'historique.

    Format d'une ligne :
        <timestamp_iso> exit=<code> nihil <args...>

    Tu peux ensuite ouvrir history.log et copier directement
    la partie `nihil ...` pour rejouer la commande.
    """
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        command_str = "nihil " + " ".join(argv)
        line = f"{command_str}\n"
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # L'historique ne doit jamais casser la CLI
        return

