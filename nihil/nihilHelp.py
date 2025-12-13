#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Help and documentation for Nihil"""

import argparse
from nihil import __version__


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
    start_parser.add_argument("--network", help="Network mode (e.g., host)")
    start_parser.add_argument("--workspace", help="Workspace path to mount")
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
    remove_parser.add_argument("names", nargs="+", help="Container name(s)")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    
    # Command: exec
    exec_parser = subparsers.add_parser(
        "exec",
        help="Execute a command in a container"
    )
    exec_parser.add_argument("name", help="Container name")
    exec_parser.add_argument("command", nargs="*", help="Command to execute (default: bash)")
    
    return parser

