#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bannière Nihil — TheNullPigeons."""

import sys
from typing import Optional


def get_banner() -> str:
    banner = """
    ╔═══════════════════════════════════════════════╗
    ║     ███╗   ██╗██╗██╗  ██╗██╗██╗     ██╗       ║
    ║     ████╗  ██║██║██║  ██║██║██║     ██║       ║
    ║     ██╔██╗ ██║██║███████║██║██║     ██║       ║
    ║     ██║╚██╗██║██║██╔══██║██║██║     ██║       ║
    ║     ██║ ╚████║██║██║  ██║██║███████╗███████╗  ║
    ║     ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝  ║
    ║                                               ║
    ║            by 0xbbuddha and Goultarde         ║
    ║                 TheNullPigeons                ║
    ╚═══════════════════════════════════════════════╝
    """
    return banner


def print_banner(file: Optional[object] = None) -> None:
    if file is None:
        file = sys.stdout
    print(get_banner(), file=file, end='')


def get_compact_banner() -> str:
    return """
    ╔═══════════════════════════════════════════════╗
    ║  NIHIL - TheNullPigeons                       ║
    ║                                               ║
    ║   by 0xbbuddha and Goultarde                  ║
    ║   TheNullPigeons                              ║
    ╚═══════════════════════════════════════════════╝
    """


def print_compact_banner(file: Optional[object] = None) -> None:
    if file is None:
        file = sys.stdout
    print(get_banner(), file=file, end='')
