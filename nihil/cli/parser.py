#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser CLI Nihil: sous-commandes et arguments."""

import argparse

from nihil import __version__

try:
    import argcomplete  # type: ignore
except Exception:
    argcomplete = None


class _ContainerOptionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            namespace.containers = True
        else:
            namespace.container = values


class _ExplicitValueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, f"{self.dest}_explicit", True)


def _add_start_options(parser: argparse.ArgumentParser) -> None:
    privilege = parser.add_mutually_exclusive_group()
    privilege.add_argument("--privileged", dest="privileged", action="store_true", default=None, help="Privileged mode")
    privilege.add_argument("--standard", dest="privileged", action="store_false", help="Disable privileged mode")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--network", default=None, metavar="NAME", help="Docker network name or mode: docker, host, disabled, or nat (default: from config)")
    network.add_argument("--host", dest="network", action="store_const", const="host", help="Use the host network")
    parser.add_argument("--image", default=None, metavar="VARIANT", help="Image variant to use (full|ad|web|blueteam or nihil/<variant>:local). If not specified, you will be prompted to select one.")
    parser.add_argument("--workspace", "-w", default=None, help="Workspace path to mount")
    parser.add_argument("--workspace-here", action="store_true", default=None, help="Mount the current working directory as /workspace inside the container.")
    scripts = parser.add_mutually_exclusive_group()
    scripts.add_argument("--script", action="store_true", help="Choose startup scripts interactively.")
    scripts.add_argument("--startup-script", action="append", default=None, metavar="NAME", help="Run this startup script (repeatable; use for non-interactive selection).")
    vpn = parser.add_mutually_exclusive_group()
    vpn.add_argument("--vpn", nargs="?", const=True, metavar="FILE", default=None, help="Start the container with OpenVPN. With FILE, use that .ovpn file; without FILE, use ~/.nihil/vpn/client.ovpn or the only .ovpn in ~/.nihil/vpn.")
    vpn.add_argument("--no-vpn", dest="vpn", action="store_false", help="Disable VPN")
    parser.add_argument("--env", "-e", action="append", metavar="KEY[=VALUE]", default=None, help="Set an environment variable in the container (repeatable). Without VALUE, forwards the value from the host environment.")
    x11 = parser.add_mutually_exclusive_group()
    x11.add_argument("--enable-x11", dest="disable_x11", action="store_false", default=None, help="Enable X11/XWayland forwarding.")
    x11.add_argument("--disable-x11", dest="disable_x11", action="store_true", help="Disable X11/XWayland forwarding for this container.")
    wayland = parser.add_mutually_exclusive_group()
    wayland.add_argument("--enable-wayland", dest="disable_wayland", action="store_false", default=None, help="Enable Wayland forwarding.")
    wayland.add_argument("--disable-wayland", dest="disable_wayland", action="store_true", help="Disable Wayland socket forwarding for this container.")
    my_resources = parser.add_mutually_exclusive_group()
    my_resources.add_argument("--my-resources", dest="no_my_resources", action="store_false", default=None, help="Mount '~/.nihil/my-resources'.")
    my_resources.add_argument("--no-my-resources", dest="no_my_resources", action="store_true", help="Do not mount '~/.nihil/my-resources' into the container.")
    nihil_resources = parser.add_mutually_exclusive_group()
    nihil_resources.add_argument("--nihil-resources", dest="no_nihil_resources", action="store_false", default=None, help="Mount the shared nihil-resources catalog.")
    nihil_resources.add_argument("--no-nihil-resources", dest="no_nihil_resources", action="store_true", help="Do not mount the shared 'nihil-resources' catalog into the container.")
    browser_ui = parser.add_mutually_exclusive_group()
    browser_ui.add_argument("--browser-ui", dest="browser_ui", action="store_true", default=None, help="Expose a browser-based UI (noVNC) for this session.")
    browser_ui.add_argument("--no-browser-ui", dest="browser_ui", action="store_false", help="Disable the browser UI.")
    parser.add_argument("--browser-ui-resolution", choices=("1280x720", "1920x1080", "2560x1440"), default="1280x720", metavar="SIZE", action=_ExplicitValueAction, help="Browser UI desktop resolution (default: 1280x720).")
    parser.set_defaults(browser_ui_resolution_explicit=False)
    parser.add_argument("--browser-ui-port", type=int, default=None, metavar="PORT", help="Port for the browser UI (default: random 6901-6999 if not set).")
    parser.add_argument("--browser-ui-password", type=str, default=None, metavar="PASSWORD", help="Password for browser UI session (default: random, shown once when ready).")
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument("--log", "-l", dest="log", action="store_true", default=None, help="Enable shell logging (asciinema)")
    logging.add_argument("--no-log", dest="log", action="store_false", help="Disable shell logging")
    tmux = parser.add_mutually_exclusive_group()
    tmux.add_argument("--tmux", dest="tmux", action="store_true", default=None, help="Open the container shell in tmux for this session.")
    tmux.add_argument("--no-tmux", dest="tmux", action="store_false", help="Do not use tmux.")
    shell = parser.add_mutually_exclusive_group()
    shell.add_argument("--no-shell", dest="no_shell", action="store_true", default=None, help="Don't open shell after starting")
    shell.add_argument("--shell", dest="no_shell", action="store_false", help="Open a shell after starting")


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
  nihil start pentest --verbose        Show detailed startup information
  nihil exec pentest                   Connect to a container
  nihil remove test1 test2 --force     Remove multiple containers
  nihil uninstall                      Remove default image
  nihil update                         Update all installed images
  nihil update ad                      Update the ad image only
  nihil upgrade                        Upgrade all nihil containers (interactive)
  nihil restart pentest                Restart a specific container
  nihil restart pentest blueteam       Restart multiple containers
  nihil upgrade pentest                Upgrade a specific container
  nihil upgrade pentest blueteam        Upgrade multiple containers
  nihil upgrade pentest -e TOKEN=abc   Recreate a container with an extra env var
  nihil exec pentest -e DEBUG=1 -- env Run a command with an extra env var
  nihil resources install              Clone the shared nihil-resources catalog
  nihil resources update               git pull the local nihil-resources catalog
  nihil resources sync                 Fetch tools listed in catalog/resources.toml
  nihil resources status               Show local nihil-resources status
  nihil image list                    List available and local image variants
  nihil image status                  Show configured image sources
  nihil image customize               Select tools for a personal image branch
  nihil image customize full --git-del
                                      Recreate the local clone and reuse its remote branch
  nihil image switch upstream          Use the upstream nihil-images source
  nihil image switch personal          Use the personal fork source
  nihil image channel dev              Pull upstream development images
  nihil image channel main             Return to stable upstream images
  nihil build full                   Build the active remote source locally with Docker
  nihil build                         Show only major Docker build steps
  nihil build -v                      Show complete Docker build output
  nihil build ad --source owner/repo --ref dev
                                      Clone a remote branch and build it locally

        """
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", metavar="COMMAND")

    info_parser = subparsers.add_parser("info", help="Display information about images and containers", allow_abbrev=False)
    info_options = info_parser.add_mutually_exclusive_group()
    info_options.add_argument(
        "-c", "--containers", nargs="?", const=None, metavar="NAME", action=_ContainerOptionAction,
        help="Show only containers; pass NAME for that container's details",
    )
    info_options.add_argument("-i", "--images", action="store_true", help="Show only images")
    info_parser.set_defaults(containers=False, images=False, container=None)

    # Backward-compatible alias; omitted from help in favor of `nihil image list`.
    subparsers.add_parser("images")

    image_parser = subparsers.add_parser("image", help="Manage image variants, sources and channels")
    image_subparsers = image_parser.add_subparsers(dest="image_action", metavar="ACTION")
    image_subparsers.add_parser("list", help="List available and local image variants")
    customize_parser = image_subparsers.add_parser(
        "customize", help="Select tools for a personal nihil-images branch"
    )
    customize_parser.add_argument(
        "variant", choices=["full", "ad", "web", "blueteam"], default="full", nargs="?",
        help="Image variant whose source branch should be customized (default: full)",
    )
    customize_parser.add_argument(
        "--no-push", action="store_true", help="Prepare the branch locally without committing or pushing"
    )
    customize_selection = customize_parser.add_mutually_exclusive_group()
    customize_selection.add_argument(
        "--web", action="store_true", help="Select tools in a local browser instead of the terminal UI"
    )
    customize_selection.add_argument(
        "--keep-tools", action="store_true", help="Reuse the saved tool selection without opening a selector"
    )
    customize_parser.add_argument(
        "--repo", default=None, metavar="REPO",
        help="GitHub repository (owner/repo or URL; default: TheNullPigeons/nihil-images)",
    )
    customize_parser.add_argument(
        "--branch", default=None, metavar="BRANCH",
        help="Upstream branch to customize and merge (default: repository default branch)",
    )
    customize_parser.add_argument(
        "--git-protocol", choices=["ssh", "https", "auto"], default="auto",
        help="Git remote protocol (default: auto, follows your gh CLI configuration)",
    )
    customize_parser.add_argument(
        "--git-del", nargs="?", choices=["local", "distant", "all"], const="local", default=False,
        help=("Delete resources before setup: local clone, distant branch and GHCR "
              "packages, or all (default when flag is used: local)"),
    )
    switch_parser = image_subparsers.add_parser("switch", help="Switch the active image source")
    switch_parser.add_argument("source", choices=["upstream", "personal"])
    channel_parser = image_subparsers.add_parser("channel", help="Select upstream image channel")
    channel_parser.add_argument("channel", choices=["main", "dev"], nargs="?", help="Channel to use (omit to show current channel)")
    image_subparsers.add_parser("status", help="Show configured upstream and personal image sources")
    image_build = image_subparsers.add_parser("build", help="Trigger a GitHub Actions image build")
    image_build.add_argument("variant", choices=["all", "full", "ad", "web", "blueteam"], nargs="?", default="all", help="Image variant to build (default: all)")
    image_build.add_argument("--wait", action="store_true", help="Wait until the GitHub Actions build finishes")
    image_build.add_argument("--web", action="store_true", help="Configure and follow the GitHub Actions build in a local browser page")
    image_build.add_argument("--allow-tool-failures", action="store_true", help="Continue after non-core tool failures and keep a report in the image")
    subparsers.add_parser("version", help="Display Nihil version")

    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics checks (Docker, image, environment)")
    doctor_output = doctor_parser.add_mutually_exclusive_group()
    doctor_output.add_argument(
        "--report", nargs="?", const="", default=None, metavar="FILE",
        help="Also save a Markdown report to paste in an issue or PR, to FILE or ./nihil-doctor-<date>.md "
             "('-' prints it instead). Container names, VPN configs, user and host names are masked.",
    )
    doctor_output.add_argument("--json", action="store_true", help="Print the results as JSON (not masked)")

    start_parser = subparsers.add_parser("start", help="Start a container (creates it if it doesn't exist)")
    start_parser.add_argument("name", help="Container name")
    start_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed startup steps and container information")
    _add_start_options(start_parser)
    start_parser.add_argument("--vpn-user", metavar="USER", default=None, help="VPN username, for configs that use auth-user-pass. Prompts for the password unless --vpn-pass is given.")
    start_parser.add_argument("--vpn-pass", metavar="PASSWORD", default=None, help="VPN password (visible in shell history and ps; prefer the prompt).")
    start_parser.add_argument(
        "--preset", nargs="?", const="", default=None, metavar="NAME",
        help="Use a saved config preset for this new container; omit NAME to choose interactively.",
    )
    stop_parser = subparsers.add_parser("stop", help="Stop one or more containers")
    stop_parser.add_argument("names", nargs="+", help="Container name(s)")

    restart_parser = subparsers.add_parser("restart", help="Restart one or more containers (stop + start)")
    restart_parser.add_argument("names", nargs="+", help="Container name(s)")
    restart_parser.add_argument("--browser-ui-resolution", choices=("1280x720", "1920x1080", "2560x1440"), default=None, metavar="SIZE", help="Recreate Browser UI at this desktop resolution.")
    restart_parser.add_argument("--no-shell", action="store_true", help="Don't open shell after restarting")

    remove_parser = subparsers.add_parser("remove", help="Remove one or more containers")
    remove_parser.add_argument("names", nargs="*", help="Container name(s)")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    remove_parser.add_argument("--wipe", action="store_true", help="Also permanently delete each container's /workspace directory on the host (asks for confirmation unless --force is also set)")

    install_parser = subparsers.add_parser("install", help="Install or update nihil images")
    install_parser.add_argument("image", nargs="?", default=None, metavar="VARIANT", help="Image variant to install (full|ad|web|blueteam). If not specified, prompted to select.")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove nihil images")
    uninstall_parser.add_argument("names", nargs="*", help="Image name(s) or numbered selections/ranges (e.g. 2-10,12-14)")
    uninstall_parser.add_argument("--unused", action="store_true", help="Remove only Nihil images unused by any container, including stopped containers")
    uninstall_parser.add_argument("--force", "-f", action="store_true", help="Force removal (with --unused: skip confirmation only)")

    update_parser = subparsers.add_parser("update", help="Update installed nihil images")
    update_parser.add_argument("image", choices=["full", "ad", "web", "blueteam"], nargs="?", default=None, help="Image variant to update. If not specified, all installed images are updated.")

    upgrade_parser = subparsers.add_parser("upgrade", help="Recreate one or more containers from the current local image (use --pull to also fetch the latest from the registry)")
    upgrade_parser.add_argument("names", nargs="*", help="Container name(s) to upgrade. If not specified, prompted to select.")
    upgrade_parser.add_argument("--force", "-f", action="store_true", help="Force upgrade/recreation even if image is already up to date")
    upgrade_parser.add_argument("--pull", "-p", action="store_true", help="Pull the latest image from the registry before recreating (default: use the existing local image)")
    upgrade_parser.add_argument("--all", action="store_true", help="Upgrade all Nihil containers without prompting.")
    upgrade_parser.add_argument("--start", action="store_true", help="Open a shell in the container after upgrading. Only valid when upgrading one container.")
    upgrade_parser.add_argument("--image", "-i", choices=["full", "ad", "web", "blueteam"], default=None, help="Change the container's image variant to the specified one during the upgrade.")
    upgrade_privilege = upgrade_parser.add_mutually_exclusive_group()
    upgrade_privilege.add_argument("--privileged", action="store_true", help="Recreate the container in privileged mode.")
    upgrade_privilege.add_argument("--standard", action="store_true", help="Recreate the container without privileged mode.")
    upgrade_parser.add_argument("--network", choices=["docker", "host", "disabled", "nat"], default=None, help="Change network mode during the upgrade.")
    upgrade_parser.add_argument("--workspace", "-w", default=None, metavar="PATH", help="Change the host path mounted as /workspace.")
    upgrade_parser.add_argument("--workspace-here", "-W", action="store_true", help="Mount the current working directory as /workspace during the upgrade.")
    upgrade_parser.add_argument("--env", "-e", action="append", default=None, metavar="KEY[=VALUE]", help="Add or override an environment variable in the recreated container (repeatable). Without VALUE, forwards the value from the host environment.")

    exec_parser = subparsers.add_parser("exec", help="Execute a command in a container")
    exec_parser.add_argument("name", help="Container name")
    exec_parser.add_argument("--env", "-e", action="append", default=None, metavar="KEY[=VALUE]", help="Set an environment variable for this command only (repeatable). Without VALUE, forwards the value from the host environment.")
    exec_parser.add_argument("exec_command", nargs="*", help="Command to execute (default: zsh)")

    tools_parser = subparsers.add_parser("tools", help="List tools available in a nihil image")
    tools_parser.add_argument("image", choices=["full", "ad", "active-directory", "web", "blueteam"], nargs="?", default=None, help="Image variant (default: full)")
    tools_parser.add_argument("--category", "-c", default=None, help="Filter by category (e.g. redteam_ad, redteam_web)")

    config_parser = subparsers.add_parser("config", help="Show or edit the Nihil configuration file")
    config_parser.add_argument("--edit", "-e", action="store_true", help="Open the config file in $EDITOR")
    config_subparsers = config_parser.add_subparsers(dest="config_action", metavar="ACTION")
    preset_parser = config_subparsers.add_parser("preset", help="Create and manage config presets")
    preset_subparsers = preset_parser.add_subparsers(dest="preset_action", required=True, metavar="ACTION")
    preset_create = preset_subparsers.add_parser("create", help="Create a preset without changing config.yml")
    preset_create.add_argument("name", help="Preset name")
    _add_start_options(preset_create)
    preset_save = preset_subparsers.add_parser("save", help="Save the current config as a named preset")
    preset_save.add_argument("name", help="Preset name")
    preset_save.add_argument("--force", action="store_true", help="Replace an existing preset")
    preset_subparsers.add_parser("list", help="List saved config presets")
    preset_edit = preset_subparsers.add_parser("edit", help="Edit a saved config preset")
    preset_edit.add_argument("name", help="Preset name")
    preset_delete = preset_subparsers.add_parser("delete", help="Delete a saved config preset")
    preset_delete.add_argument("name", help="Preset name")

    build_parser = subparsers.add_parser(
        "build", help="Build a nihil image locally, optionally showing progress in a browser",
        description=("Build locally with Docker. By default, use build.images_path or the current "
                     "nihil-images checkout; otherwise clone the active remote source and branch."),
    )
    build_parser.add_argument("variant", choices=["full", "ad", "blueteam", "web", "test"], nargs="?", default="full", help="Image variant to build (default: full)")
    build_parser.add_argument("--source", "-s", metavar="PATH|REPO", default=None, help="Local source directory or remote Git repository (overrides configured source)")
    build_parser.add_argument("--ref", metavar="REF", default=None, help="Remote branch or tag (default: active source branch/channel)")
    build_parser.add_argument("--no-cache", action="store_true", help="Pass --no-cache to docker build")
    build_parser.add_argument("--verbose", "-v", action="store_true", help="Show complete Docker build output (default: major steps only)")
    build_parser.add_argument("--web", action="store_true", help="Configure the local Docker build and follow progress in a browser")
    build_parser.add_argument("--allow-tool-failures", action="store_true", help="Continue after non-core tool failures and keep a report in the image")
    build_parser.add_argument("--tag", "-t", metavar="TAG", default=None, help="Custom image tag (default: nihil/<variant>:local)")
    build_parser.add_argument("--log", "-l", metavar="FILE", default=None, help="Write build output to a log file (use 'tail -f FILE' to follow)")

    resources_parser = subparsers.add_parser("resources", help="Manage the shared nihil-resources catalog")
    resources_subparsers = resources_parser.add_subparsers(dest="resources_action", metavar="ACTION")
    resources_install = resources_subparsers.add_parser("install", help="Clone the nihil-resources repository locally")
    resources_install.add_argument("--path", "-p", default=None, metavar="PATH", help="Destination path (default: from config, fallback: ~/.nihil/nihil-resources)")
    resources_install.add_argument("--force", "-f", action="store_true", help="Re-clone even if the destination already exists (after confirmation)")
    resources_update = resources_subparsers.add_parser("update", help="git pull the local nihil-resources repository")
    resources_sync = resources_subparsers.add_parser("sync", help="Run the nihil-resources scripts/sync.py to fetch enabled tools")
    resources_sync.add_argument("--profile", default=None, help="Restrict sync to a profile (full|ad|web|blueteam)")
    resources_sync.add_argument("--verbose", "-v", action="store_true", help="Show the full per-resource output instead of a summary")
    resources_subparsers.add_parser("status", help="Show local nihil-resources status (path, branch, last commit)")

    completion_parser = subparsers.add_parser("completion", help="Generate shell completion script")
    completion_parser.add_argument("shell", choices=["bash", "zsh"], help="Target shell for completion script (bash or zsh)")

    if argcomplete is not None:
        try:
            argcomplete.autocomplete(parser)
        except Exception:
            pass
    return parser
