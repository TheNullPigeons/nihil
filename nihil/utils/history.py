#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Historique des commandes Nihil."""

from __future__ import annotations

from pathlib import Path
from typing import List


HISTORY_PATH = Path.home() / ".config" / "nihil" / "history.log"


def log_command(argv: List[str], exit_code: int) -> None:
    """Ajoute une entrée lisible dans l'historique."""
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        command_str = "nihil " + " ".join(argv)
        line = f"{command_str}\n"
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        return
