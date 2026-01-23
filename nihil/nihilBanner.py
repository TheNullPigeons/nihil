#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banner display for Nihil - TheNullPigeons"""

import sys
from typing import Optional


def get_banner() -> str:
    """Generate the Nihil banner with pigeons"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     ███╗   ██╗██╗██╗  ██╗██╗██╗     ██╗                      ║
    ║     ████╗  ██║██║██║  ██║██║██║     ██║                      ║
    ║     ██╔██╗ ██║██║███████║██║██║     ██║                      ║
    ║     ██║╚██╗██║██║██╔══██║██║██║     ██║                      ║
    ║     ██║ ╚████║██║██║  ██║██║███████╗███████╗                 ║
    ║     ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝                 ║
    ║                                                              ║
    ║            by 0xbbuddha and Goultarde                      ║
    ║                 TheNullPigeons                              ║
    ║                                                              ║
    ║        ⠀⠀⣀⠤⠤⠤⢄⡀⠀⠀⠀⠀⠀⠀⠀⠀                                   ║
    ║        ⠀⡠⠋⠒⠀⠟⠀⠇⠀⠀⠀⠀⠀⠀⠀⠀                                   ║
    ║        ⠓⠐⠒⡖⠒⠂⠀⣇⣀⡀⠀⠀⠀⠀⠀⠀                                   ║
    ║        ⠀⠀⢰⠃⠀⠀⠀⡇⠀⠈⢳⠀⠀⠀⠀⠀                                  ║
    ║        ⠀⠀⠈⣇⠀⠀⠀⠈⠓⣄⣀⡧⡀⣀⡀⡀                                  ║
    ║        ⠀⠀⠀⠉⡗⠦⢶⠒⠒⠒⠉⠉⠁⠀⠀                                    ║
    ║        ⠀⠀⠀⠒⠃⠠⠼⠀⠀⠀⠀⠀⠀⠀⠀                                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    return banner


def print_banner(file: Optional[object] = None) -> None:
    """Print the Nihil banner"""
    if file is None:
        file = sys.stdout
    
    banner = get_banner()
    print(banner, file=file, end='')


def get_compact_banner() -> str:
    """Generate a compact version of the banner"""
    return """
    ╔═══════════════════════════════════════════════╗
    ║  NIHIL - TheNullPigeons                       ║
    ║                                               ║
    ║  ⠀⠀⣀⠤⠤⠤⢄⡀⠀⠀⠀⠀⠀⠀⠀⠀                             ║
    ║  ⠀⡠⠋⠒⠀⠟⠀⠇⠀⠀⠀⠀⠀⠀⠀⠀                             ║
    ║  ⠓⠐⠒⡖⠒⠂⠀⣇⣀⡀⠀⠀⠀⠀⠀⠀                             ║
    ║  ⠀⠀⢰⠃⠀⠀⠀⡇⠀⠈⢳⠀⠀⠀⠀⠀                             ║
    ║  ⠀⠀⠈⣇⠀⠀⠀⠈⠓⣄⣀⡧⡀⣀⡀⡀                             ║
    ║  ⠀⠀⠀⠉⡗⠦⢶⠒⠒⠒⠉⠉⠁⠀⠀                              ║
    ║  ⠀⠀⠀⠒⠃⠠⠼⠀⠀⠀⠀⠀⠀⠀⠀                              ║
    ║                                               ║
    ║   by 0xbbuddha and Goultarde                  ║
    ║   TheNullPigeons                              ║
    ╚═══════════════════════════════════════════════╝
    """


def print_compact_banner(file: Optional[object] = None) -> None:
    """Print a compact version of the banner"""
    if file is None:
        file = sys.stdout
    
    banner = get_compact_banner()
    print(banner, file=file, end='')
