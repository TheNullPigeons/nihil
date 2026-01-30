#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Help and documentation for Nihil"""

import argparse
from nihil import __version__

try:
    # Optionnel : si argcomplete est installé, on active l'auto-complétion
    import argcomplete  # type: ignore
except Exception:  # pragma: no cover - complétion ne doit jamais casser la CLI
    argcomplete = None


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        prog="nihil",
        description="Nihil - by 0xbbuddha and Goultarde",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nihil --version                      Display version
  nihil --help                         Display this help
  nihil info                           Show images and containers
  nihil start pentest --privileged     Start a privileged container
  nihil exec pentest                   Connect to a container
  nihil remove test1 test2 --force     Remove multiple containers
  nihil uninstall                      Remove default image
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="COMMAND"
    )
    
    # Command: info
    info_parser = subparsers.add_parser(
        "info",
        help="Display information about images and containers"
    )
    
    # Command: images
    images_parser = subparsers.add_parser(
        "images",
        help="List available image variants"
    )
    
    # Command: version
    version_parser = subparsers.add_parser(
        "version",
        help="Display Nihil version"
    )

    # Command: doctor
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run diagnostics checks (Docker, image, environment)"
    )
    
    # Command: start
    start_parser = subparsers.add_parser(
        "start",
        help="Start a container (creates it if it doesn't exist)"
    )
    start_parser.add_argument("name", help="Container name")
    start_parser.add_argument("--privileged", action="store_true", help="Privileged mode")
    start_parser.add_argument(
        "--network", 
        choices=["docker", "host", "disabled", "nat"],
        default="host",
        help="Network mode (default: host)"
    )
    start_parser.add_argument(
        "--image",
        choices=["base", "ad", "active-directory", "web", "crypto"],
        default=None,
        help="Image variant to use. If not specified, you will be prompted to select one."
    )
    start_parser.add_argument("--workspace", help="Workspace path to mount")
    start_parser.add_argument("--log", "-l", action="store_true", help="Enable shell logging (asciinema)")
    start_parser.add_argument("--no-shell", action="store_true", help="Don't open shell after starting")
    
    # Command: stop
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop a container"
    )
    stop_parser.add_argument("name", help="Container name")
    
    # Command: remove
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove one or more containers"
    )
    remove_parser.add_argument("names", nargs="*", help="Container name(s)")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    
    # Command: install
    install_parser = subparsers.add_parser(
        "install",
        help="Install or update nihil images"
    )
    install_parser.add_argument(
        "image",
        choices=["base", "ad", "active-directory", "web", "crypto"],
        nargs="?",
        default=None,
        help="Image variant to install. If not specified, prompted to select."
    )
    
    # Command: uninstall
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove nihil images"
    )
    uninstall_parser.add_argument("names", nargs="*", help="Image name(s)")
    uninstall_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    
    # Command: exec
    exec_parser = subparsers.add_parser(
        "exec",
        help="Execute a command in a container"
    )
    exec_parser.add_argument("name", help="Container name")
    exec_parser.add_argument("command", nargs="*", help="Command to execute (default: bash)")

    # Command: completion
    completion_parser = subparsers.add_parser(
        "completion",
        help="Generate shell completion script"
    )
    completion_parser.add_argument(
        "shell",
        choices=["bash", "zsh"],
        help="Target shell for completion script (bash or zsh)"
    )
    
    # Activer l'auto-complétion si argcomplete est disponible
    if argcomplete is not None:
        try:
            argcomplete.autocomplete(parser)
        except Exception:
            # On ignore toute erreur de complétion pour ne pas impacter la CLI
            pass
    
    return parser

