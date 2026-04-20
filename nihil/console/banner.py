#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bannière Nihil: TheNullPigeons."""

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
    return "  NIHIL  ·  TheNullPigeons\n  by 0xbbuddha and Goultarde"


def print_compact_banner(file: Optional[object] = None) -> None:
    if file is None:
        file = sys.stdout
    try:
        from rich.console import Console
        console = Console(file=file)
        console.print(
            "\n  [bold #d2ac7e]NIHIL[/]  [dim]·[/]  [#d2ac7e]TheNullPigeons[/]"
            "\n  [dim]by 0xbbuddha and Goultarde[/]\n",
            highlight=False,
        )
    except ImportError:
        print(get_compact_banner(), file=file)
