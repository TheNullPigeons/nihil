#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser CLI Nihil: sous-commandes et arguments."""

import argparse

from nihil import __version__

try:
    import argcomplete  # type: ignore
except Exception:
    argcomplete = None


def create_parser() -> argparse.ArgumentParser:
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
  nihil update                         Update all installed images
  nihil update ad                      Update the ad image only
  nihil upgrade                        Upgrade all nihil containers (interactive)
  nihil upgrade pentest                Upgrade a specific container
  nihil upgrade pentest ctf            Upgrade multiple containers

        """
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", metavar="COMMAND")

    info_parser = subparsers.add_parser("info", help="Display information about images and containers")
    info_parser.add_argument("--container", "-c", metavar="NAME", help="Show detailed information for a specific container")

    subparsers.add_parser("images", help="List available image variants")

    subparsers.add_parser("version", help="Display Nihil version")

    subparsers.add_parser("doctor", help="Run diagnostics checks (Docker, image, environment)")

    start_parser = subparsers.add_parser("start", help="Start a container (creates it if it doesn't exist)")
    start_parser.add_argument("name", help="Container name")
    start_parser.add_argument("--privileged", action="store_true", help="Privileged mode")
    start_parser.add_argument("--network", choices=["docker", "host", "disabled", "nat"], default=None, help="Network mode (default: from config, fallback: host)")
    start_parser.add_argument("--image", choices=["full", "ad", "web", "ctf"], default=None, help="Image variant to use. If not specified, you will be prompted to select one.")
    start_parser.add_argument("--workspace", help="Workspace path to mount")
    start_parser.add_argument("--workspace-here", action="store_true", help="Mount the current working directory as /workspace inside the container.")
    start_parser.add_argument("--vpn", metavar="FILE", default=None, help="Path to OpenVPN config file (.ovpn). Starts the container with VPN; VPN stops when you exit the container.")
    start_parser.add_argument("--enable-x11", action="store_true", help="Enable X11/XWayland GUI support (mount host X socket and forward DISPLAY).")
    start_parser.add_argument("--no-my-resources", action="store_true", help="Do not mount '~/.nihil/my-resources' into the container.")
    start_parser.add_argument("--browser-ui", action="store_true", help="Expose a browser-based UI (noVNC) for this session.")
    start_parser.add_argument("--browser-ui-port", type=int, default=None, metavar="PORT", help="Port for the browser UI (default: random 6901-6999 if not set).")
    start_parser.add_argument("--browser-ui-password", type=str, default=None, metavar="PASSWORD", help="Password for browser UI session (default: random, shown once when ready).")
    start_parser.add_argument("--log", "-l", action="store_true", help="Enable shell logging (asciinema)")
    start_parser.add_argument("--no-shell", action="store_true", help="Don't open shell after starting")

    stop_parser = subparsers.add_parser("stop", help="Stop a container")
    stop_parser.add_argument("name", help="Container name")

    remove_parser = subparsers.add_parser("remove", help="Remove one or more containers")
    remove_parser.add_argument("names", nargs="*", help="Container name(s)")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force removal")

    install_parser = subparsers.add_parser("install", help="Install or update nihil images")
    install_parser.add_argument("image", choices=["full", "ad", "web", "ctf"], nargs="?", default=None, help="Image variant to install. If not specified, prompted to select.")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove nihil images")
    uninstall_parser.add_argument("names", nargs="*", help="Image name(s)")
    uninstall_parser.add_argument("--force", "-f", action="store_true", help="Force removal")

    update_parser = subparsers.add_parser("update", help="Update installed nihil images")
    update_parser.add_argument("image", choices=["full", "ad", "web", "ctf"], nargs="?", default=None, help="Image variant to update. If not specified, all installed images are updated.")

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade one or more containers to the latest image version")
    upgrade_parser.add_argument("names", nargs="*", help="Container name(s) to upgrade. If not specified, prompted to select.")
    upgrade_parser.add_argument("--force", "-f", action="store_true", help="Force upgrade/recreation even if image is already up to date")
    upgrade_parser.add_argument("--image", "-i", choices=["full", "ad", "web", "ctf"], default=None, help="Change the container's image variant to the specified one during the upgrade.")

    exec_parser = subparsers.add_parser("exec", help="Execute a command in a container")
    exec_parser.add_argument("name", help="Container name")
    exec_parser.add_argument("command", nargs="*", help="Command to execute (default: zsh)")

    tools_parser = subparsers.add_parser("tools", help="List tools available in a nihil image")
    tools_parser.add_argument("image", choices=["full", "ad", "active-directory", "web", "ctf"], nargs="?", default=None, help="Image variant (default: full)")
    tools_parser.add_argument("--category", "-c", default=None, help="Filter by category (e.g. redteam_ad, redteam_web)")

    config_parser = subparsers.add_parser("config", help="Show or edit the Nihil configuration file")
    config_parser.add_argument("--edit", "-e", action="store_true", help="Open the config file in $EDITOR")

    completion_parser = subparsers.add_parser("completion", help="Generate shell completion script")
    completion_parser.add_argument("shell", choices=["bash", "zsh"], help="Target shell for completion script (bash or zsh)")

    if argcomplete is not None:
        try:
            argcomplete.autocomplete(parser)
        except Exception:
            pass
    return parser
