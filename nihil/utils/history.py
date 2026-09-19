#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil command history."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


HISTORY_PATH = Path.home() / ".config" / "nihil" / "history.log"

# Options whose value can identify a client or contain a secret
# (VPN file, workspace path, --env variables...). This file is never
# purged automatically (not even by `nihil remove`), so their values
# are never logged in clear text.
_REDACT_FLAGS = {"--env", "-e", "--vpn", "--workspace", "-w", "--browser-ui-password"}


def _redact(argv: List[str]) -> List[str]:
    """Replace the value of sensitive options with '***' before logging."""
    redacted: List[str] = []
    pending_flag: Optional[str] = None
    for token in argv:
        if pending_flag is not None:
            flag, pending_flag = pending_flag, None
            if flag == "--vpn" and token.startswith("-"):
                # --vpn has an optional value: this token is another option, not its value.
                redacted.append(token)
                continue
            redacted.append("***")
            continue
        flag, sep, _value = token.partition("=")
        if sep and flag in _REDACT_FLAGS:
            redacted.append(f"{flag}=***")
            continue
        if token in _REDACT_FLAGS:
            redacted.append(token)
            pending_flag = token
            continue
        redacted.append(token)
    return redacted


def log_command(argv: List[str], exit_code: int) -> None:
    """Append a readable entry to the history (sensitive values masked)."""
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        command_str = "nihil " + " ".join(_redact(argv))
        line = f"{command_str}\n"
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        return
