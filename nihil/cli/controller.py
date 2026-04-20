#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controller CLI Nihil: point d'entrée et dispatch des commandes."""

import os
import secrets
import sys
import time
from pathlib import Path
from typing import List, Optional

from nihil.config import ensure_filesystem, NihilConfig
from nihil.features.browser_ui import (
    save_password as browser_ui_save_password,
    load_password as browser_ui_load_password,
    clear_password as browser_ui_clear_password,
    get_session_str_for_recap as browser_ui_get_session_str,
    is_page_ready as browser_ui_is_page_ready,
)
from nihil.manager import NihilManager
from nihil.cli.parser import create_parser
from nihil.console import NihilFormatter, print_compact_banner
from nihil.exceptions import NihilError
from nihil.utils import NihilDoctor, log_command
from nihil import __version__


class NihilController:
    def __init__(self):
        ensure_filesystem()
        self.config = NihilConfig()
        self.parser = create_parser()
        self.manager = None
        self.formatter = NihilFormatter()

    def run(self, args: Optional[list] = None) -> int:
        parsed_args = self.parser.parse_args(args)
        should_show_banner = (
            parsed_args.command is not None and
            parsed_args.command not in ["version", "completion", "config"]
        )
        if should_show_banner:
            print_compact_banner()
        if parsed_args.command is None:
            self.parser.print_help()
            return 0
        if parsed_args.command == "version":
            print(f"Nihil version {__version__}")
            return 0
        if parsed_args.command == "doctor":
            doctor = NihilDoctor(formatter=self.formatter)
            return doctor.run()
        if parsed_args.command == "config":
            return self._cmd_config(parsed_args)
        try:
            self.manager = NihilManager()
        except NihilError as e:
            print(self.formatter.error(str(e)), file=sys.stderr)
            return e.exit_code
        if parsed_args.command == "info":
            return self._cmd_info(parsed_args)
        elif parsed_args.command == "images":
            return self._cmd_images()
        elif parsed_args.command == "start":
            return self._cmd_start(parsed_args)
        elif parsed_args.command == "stop":
            return self._cmd_stop(parsed_args)
        elif parsed_args.command == "remove":
            return self._cmd_remove(parsed_args)
        elif parsed_args.command == "exec":
            return self._cmd_exec(parsed_args)
        elif parsed_args.command == "update":
            return self._cmd_update(parsed_args)
        elif parsed_args.command == "install":
            return self._cmd_install(parsed_args)
        elif parsed_args.command == "uninstall":
            return self._cmd_uninstall(parsed_args)
        elif parsed_args.command == "upgrade":
            return self._cmd_upgrade(parsed_args)
        elif parsed_args.command == "tools":
            return self._cmd_tools(parsed_args)
        elif parsed_args.command == "completion":
            return self._cmd_completion(parsed_args)
        return 0

    def _cmd_start(self, args) -> int:
        _NOT_CHECKED = object()
        _update_cache = [_NOT_CHECKED]

        def get_update(c):
            if _update_cache[0] is _NOT_CHECKED:
                _update_cache[0] = self._check_image_update(c) if self.config.auto_check_updates else None
            return _update_cache[0]

        container_name = args.name
        # Appliquer les defaults de config pour les options non spécifiées par l'utilisateur
        if args.network is None:
            args.network = self.config.default_network
        if not args.enable_x11 and self.config.x11_by_default:
            args.enable_x11 = True
        if not args.no_my_resources and not self.config.my_resources_enabled:
            args.no_my_resources = True
        if not args.log and self.config.logging_always_enable:
            args.log = True
        if args.workspace is None and not args.workspace_here and self.config.default_workspace:
            args.workspace = str(self.config.default_workspace)
        print(self.formatter.info(f"Looking for container '{container_name}'..."))
        container = self.manager.get_container(container_name)
        container_existed = container is not None
        if container:
            print(self.formatter.info(f"Container '{container_name}' found."))
            if container.status == "running":
                print(self.formatter.warning(f"Container '{container_name}' is already running."))
            else:
                print(self.formatter.info(f"Starting container '{container_name}'..."))
                self.manager.start_container(container)
                print(self.formatter.success(f"Container '{container_name}' started successfully."))
            env_list = container.attrs.get("Config", {}).get("Env") or []
            delay_info = not args.no_shell and any(e == "NIHIL_BROWSER_UI=1" for e in env_list)
            if not delay_info:
                self._print_container_info(container, args, created=False, update_available=get_update(container))
        else:
            print(self.formatter.info(f"Container '{container_name}' doesn't exist. Creating..."))
            network_map = {"host": "host", "disabled": "none", "docker": "bridge", "nat": "bridge"}
            image_arg = args.image
            if image_arg is None:
                from rich.console import Console
                from rich.prompt import IntPrompt
                console = Console()
                print(self.formatter.info("No image specified. Please select one:"))
                variants = list(self.manager.AVAILABLE_IMAGES.keys())
                rows = []
                for i, variant in enumerate(variants):
                    desc = "The whole flock"
                    if "ad" in variant:
                        desc = "Active Directory tools"
                    elif "web" in variant:
                        desc = "Web Hacking tools"
                    elif "ctf" in variant:
                        desc = "Capture The Flag tools"
                    image_tag = self.manager.AVAILABLE_IMAGES[variant]
                    info = self.manager.get_image_info(image_tag)
                    if info:
                        size_gb = info["size_bytes"] / (1024 ** 3)
                        size_str = f"{size_gb:.2f} GB"
                        installed = "Yes"
                    else:
                        size_str = "-"
                        installed = "No"
                    rows.append([str(i + 1), variant, desc, size_str, installed])
                self.formatter.print_table(["#", "VARIANT", "DESCRIPTION", "SIZE", "INSTALLED"], rows)
                choices_indices = list(range(1, len(variants) + 1))
                try:
                    choice = IntPrompt.ask("Select an image", choices=[str(c) for c in choices_indices], default=1)
                    image_arg = variants[choice - 1]
                except KeyboardInterrupt:
                    print("\nAborted.")
                    return 1
            image = self.manager.AVAILABLE_IMAGES.get(image_arg, self.manager.DEFAULT_IMAGE)
            print(self.formatter.info(f"Using image variant: {image_arg} ({image})"))
            vpn_path = getattr(args, "vpn", None)
            workspace_path = args.workspace
            if workspace_path is None and getattr(args, "workspace_here", False):
                workspace_path = os.getcwd()
            
            # Utiliser le default de la config, ou créer un propre au container par défaut
            if workspace_path is None:
                if getattr(self.config, "default_workspace", None):
                    workspace_path = str(self.config.default_workspace)
                else:
                    from nihil.config.defaults import NIHIL_HOME
                    default_ws = NIHIL_HOME / "workspaces" / container_name
                    default_ws.mkdir(parents=True, exist_ok=True)
                    workspace_path = str(default_ws)

            if workspace_path is not None:
                workspace_path = str(Path(workspace_path).expanduser().resolve())
            browser_ui_enabled = getattr(args, "browser_ui", False)
            browser_ui_port = getattr(args, "browser_ui_port", None)
            if browser_ui_port is not None and not (1 <= browser_ui_port <= 65535):
                print(self.formatter.error(f"Invalid port: {browser_ui_port}. Must be between 1 and 65535."), file=sys.stderr)
                return 1
            browser_ui_password = getattr(args, "browser_ui_password", None)
            if browser_ui_enabled and browser_ui_password is None:
                browser_ui_password = secrets.token_urlsafe(12)
                browser_ui_save_password(container_name, browser_ui_password)
            container = self.manager.create_container(
                name=container_name,
                image=image,
                privileged=args.privileged,
                network_mode=network_map.get(args.network, "host"),
                workspace=workspace_path,
                vpn=bool(vpn_path),
                vpn_config_path=vpn_path,
                enable_x11=getattr(args, "enable_x11", False),
                disable_my_resources=getattr(args, "no_my_resources", False),
                my_resources_path=self.config.my_resources_path,
                browser_ui=browser_ui_enabled,
                browser_ui_port=browser_ui_port if browser_ui_enabled else None,
                browser_ui_password=browser_ui_password if browser_ui_enabled else None,
            )
            print(self.formatter.info(f"Container '{container_name}' created."))
            print(self.formatter.info(f"Starting container '{container_name}'..."))
            self.manager.start_container(container)
            print(self.formatter.success(f"Container '{container_name}' created and started successfully."))
            if not (browser_ui_enabled and not args.no_shell):
                self._print_container_info(container, args, created=True, update_available=get_update(container))
        if not args.no_shell:
            command = "zsh"
            vpn_path = getattr(args, "vpn", None)
            if container_existed and vpn_path:
                if not self.manager.container_has_tun(container):
                    print(self.formatter.error(
                        "This container has no VPN support (/dev/net/tun missing). "
                        "To use VPN, create a new container with --vpn, e.g.: nihil remove demo && nihil start demo --vpn ~/vpn/file.ovpn"
                    ))
                else:
                    vpn_file = Path(vpn_path).expanduser().resolve()
                    if vpn_file.is_file():
                        if self.manager.copy_file_into_container(container, str(vpn_file), "/tmp/nihil_vpn.ovpn"):
                            print(self.formatter.info("VPN config copied into container; VPN will start for this session and stop when you exit."))
                            command = "sh -c 'openvpn --config /tmp/nihil_vpn.ovpn --daemon >/dev/null 2>&1; sleep 2; zsh; killall openvpn >/dev/null 2>&1; exit 0'"
                        else:
                            print(self.formatter.warning("Could not copy VPN config into container. Start OpenVPN manually if needed."))
                    else:
                        print(self.formatter.warning(f"VPN file not found: {vpn_file}"))
            if args.log and command == "zsh":
                import datetime
                timestamp = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                logfile = f"/workspace/logs/{timestamp}_shell.asciinema"
                title = f"Nihil Session {timestamp}"
                self.manager.exec_in_container(container, "mkdir -p /workspace/logs")
                print(self.formatter.info(f"Logging session to {logfile}"))
                command = f"asciinema rec -i 2 --stdin --quiet --command zsh --title '{title}' {logfile}"
            env_list = container.attrs.get("Config", {}).get("Env") or []
            browser_ui_port = None
            if any(e == "NIHIL_BROWSER_UI=1" for e in env_list):
                for e in env_list:
                    if e.startswith("NIHIL_BROWSER_UI_PORT="):
                        try:
                            browser_ui_port = int(e.split("=", 1)[1])
                            break
                        except ValueError:
                            pass
            if browser_ui_port:
                print(self.formatter.info("Preparing browser UI..."))
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    if browser_ui_is_page_ready(browser_ui_port):
                        print(self.formatter.success("Browser UI ready."))
                        break
                    time.sleep(2)
                else:
                    print(self.formatter.warning("Browser UI may still be starting; open the link from the recap when ready."))
                session_str = browser_ui_get_session_str(container, container_name)
                self._print_container_info(container, args, created=not container_existed, browser_ui_session=session_str, update_available=get_update(container))
            print(self.formatter.info(f"Connecting to container '{container_name}'..."))
            self.manager.exec_in_container(container, command)
        return 0

    def _check_image_update(self, container) -> Optional[bool]:
        """Lance le check de mise à jour dans un thread avec timeout de 5s."""
        import concurrent.futures
        try:
            image_tag = container.image.tags[0] if container.image.tags else None
            if not image_tag:
                return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.manager.check_image_update, image_tag)
                return future.result(timeout=5)
        except Exception:
            return None

    def _print_container_info(self, container, args, created: bool = False, browser_ui_session: Optional[str] = None, update_available: Optional[bool] = None) -> None:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
        except ImportError:
            return
        name = container.name
        image_tag = container.image.tags[0] if container.image.tags else container.attrs.get("Config", {}).get("Image", "?")
        short_image = self.manager.short_image_name(image_tag)
        cid = container.short_id
        attrs = container.attrs
        host_config = attrs.get("HostConfig") or {}
        network_mode = host_config.get("NetworkMode") or "host"
        privileged = host_config.get("Privileged") or False
        mounts = attrs.get("Mounts") or []
        env_list = attrs.get("Config", {}).get("Env") or []
        env = {}
        for kv in env_list:
            if "=" in kv:
                k, v = kv.split("=", 1)
                env[k] = v
        workspace_mount = None
        my_resources_mount = None
        for m in mounts:
            if m.get("Destination") == "/workspace":
                workspace_mount = m.get("Source")
            if m.get("Destination") == "/opt/my-resources":
                my_resources_mount = m.get("Source")
        if network_mode == "host":
            network_display = "[yellow]host[/] (shares host network)"
        elif network_mode in ("bridge", "docker"):
            network_display = "[cyan]bridge[/]"
        elif network_mode in ("none", "disabled"):
            network_display = "[magenta]none[/]"
        else:
            network_display = network_mode
        priv_display = "[red]Yes[/]" if privileged else "[green]No[/]"
        if workspace_mount:
            workspace_display = f"[green]{workspace_mount}[/] → [cyan]/workspace[/]"
        else:
            workspace_display = "[cyan]/workspace[/] (default, no host mount)"
        if my_resources_mount:
            my_resources_display = f"[green]Enabled[/] ({my_resources_mount} → /opt/my-resources)"
        else:
            my_resources_display = "[red]Disabled[/]"
        vpn_flag = env.get("NIHIL_VPN") == "1"
        requested_session_vpn = bool(getattr(args, "vpn", None)) and not created
        has_tun = False
        try:
            has_tun = self.manager.container_has_tun(container)
        except Exception:
            has_tun = False
        if vpn_flag:
            vpn_display = "[green]Enabled[/] (NIHIL_VPN=1)"
        elif requested_session_vpn and has_tun:
            vpn_display = "[yellow]Session only[/] (config copied inside)"
        else:
            vpn_display = "[red]Disabled[/]"
        has_x11_mount = any(m.get("Destination") == "/tmp/.X11-unix" for m in mounts)
        display_env = env.get("DISPLAY")
        x_mode = env.get("NIHIL_X_MODE", "unknown")
        if has_x11_mount and display_env:
            if x_mode == "xwayland":
                x11_display = f"[green]Enabled[/] (XWayland, DISPLAY={display_env})"
            elif x_mode == "x11":
                x11_display = f"[green]Enabled[/] (X11, DISPLAY={display_env})"
            else:
                x11_display = f"[green]Enabled[/] (DISPLAY={display_env})"
        else:
            x11_display = "[red]Disabled[/]"
        browser_ui_flag = env.get("NIHIL_BROWSER_UI") == "1"
        browser_ui_port = env.get("NIHIL_BROWSER_UI_PORT") or "6901"
        if browser_ui_flag:
            browser_ui_display = f"[green]Enabled[/] (http://127.0.0.1:{browser_ui_port})"
        else:
            browser_ui_display = "[red]Disabled[/]"
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        table.add_row("Name", name)
        table.add_row("Image", short_image)
        table.add_row("Container ID", cid)
        table.add_row("Network", network_display)
        table.add_row("Privileged", priv_display)
        table.add_row("Workspace", workspace_display)
        table.add_row("My resources", my_resources_display)
        table.add_row("VPN", vpn_display)
        table.add_row("X11", x11_display)
        table.add_row("Browser UI", browser_ui_display)
        if browser_ui_flag:
            if browser_ui_session:
                table.add_row("Session (browser)", f"[green]{browser_ui_session}[/]")
            else:
                table.add_row("Session (browser)", "[dim](see browser page)[/]")
        if update_available is True:
            table.add_row("Image update", "[yellow]Update available[/] → run [bold cyan]nihil update[/]")
        elif update_available is False:
            table.add_row("Image update", "[green]Up to date[/]")
        title = "New container" if created else "Container"
        self.formatter.print_docs_hint()
        Console().print(Panel(table, title=f"[bold]{title}[/]", border_style="blue", padding=(0, 1)))

    def _cmd_stop(self, args) -> int:
        container_name = args.name
        container = self.manager.get_container(container_name)
        if not container:
            print(self.formatter.error(f"Container '{container_name}' doesn't exist."), file=sys.stderr)
            return 1
        if container.status != "running":
            print(self.formatter.warning(f"Container '{container_name}' is not running."))
            return 0
        print(self.formatter.info(f"Stopping container '{container_name}'..."))
        self.manager.stop_container(container)
        print(self.formatter.success(f"Container '{container_name}' stopped successfully."))
        return 0

    def _cmd_remove(self, args) -> int:
        container_names = args.names
        if not container_names:
            from rich.prompt import Prompt
            from rich.console import Console
            console = Console()
            nihil_containers = self.manager.list_containers(all=True)
            if not nihil_containers:
                print("No nihil containers found.")
                return 0
            selected_containers = []
            while True:
                available_containers = [c for c in nihil_containers if c.name not in selected_containers]
                if not available_containers:
                    break
                rows = []
                for c in available_containers:
                    status = c.status.capitalize()
                    try:
                        image_tag = c.image.tags[0] if c.image.tags else c.attrs['Config']['Image']
                    except Exception:
                        image_tag = c.attrs.get('Config', {}).get('Image', '<deleted image>')
                    if "/" in image_tag:
                        image_tag = image_tag.split("/")[-1]
                    config_str = "Standard"
                    if c.attrs.get("HostConfig", {}).get("Privileged"):
                        config_str = "Privileged 💥"
                    rows.append([c.name, status, image_tag, config_str])
                print("\n👽 Available containers")
                self.formatter.print_table(["NAME", "STATUS", "IMAGE", "CONFIG"], rows)
                default_choice = available_containers[0].name
                try:
                    choice = Prompt.ask("[?] Select a container by its name", choices=[c.name for c in available_containers], default=default_choice)
                    selected_containers.append(choice)
                    if not [c for c in available_containers if c.name != choice]:
                        break
                    more = Prompt.ask("[?] Do you want to select another container?", choices=["y", "n"], default="n")
                    if more.lower() != 'y':
                        break
                except (KeyboardInterrupt, EOFError):
                    print("\nAborted.")
                    return 0
            if not selected_containers:
                print("No container selected.")
                return 0
            container_names = selected_containers
        errors = 0
        for container_name in container_names:
            container = self.manager.get_container(container_name)
            if not container:
                print(self.formatter.error(f"Container '{container_name}' doesn't exist."), file=sys.stderr)
                errors += 1
                continue
            if container.status == "running":
                print(self.formatter.info(f"Stopping container '{container_name}'..."))
                self.manager.stop_container(container)
            print(self.formatter.info(f"Removing container '{container_name}'..."))
            self.manager.remove_container(container, force=args.force)
            browser_ui_clear_password(container_name)
            print(self.formatter.success(f"Container '{container_name}' removed successfully."))
        return 1 if errors > 0 else 0

    def _cmd_exec(self, args) -> int:
        container_name = args.name
        container = self.manager.get_container(container_name)
        if not container:
            print(self.formatter.error(f"Container '{container_name}' doesn't exist."), file=sys.stderr)
            return 1
        if container.status != "running":
            print(self.formatter.error(f"Container '{container_name}' is not running."), file=sys.stderr)
            return 1
        command = " ".join(args.command) if args.command else "zsh"
        self.manager.exec_in_container(container, command)
        return 0

    def _cmd_update(self, args) -> int:
        image_arg = getattr(args, "image", None)

        if image_arg:
            variants_to_update = [image_arg]
        else:
            installed = self.manager.list_images()
            if not installed:
                print(self.formatter.warning("No nihil images installed locally. Use 'nihil install' first."))
                return 0
            reverse_map = {v: k for k, v in self.manager.AVAILABLE_IMAGES.items()}
            variants_to_update = []
            for img in installed:
                for tag in img.tags:
                    if tag in reverse_map:
                        variants_to_update.append(reverse_map[tag])
                        break
            if not variants_to_update:
                print(self.formatter.warning("No updatable nihil images found."))
                return 0

        errors = 0
        containers_to_upgrade: List[str] = []

        for variant in variants_to_update:
            image_tag = self.manager.AVAILABLE_IMAGES.get(variant)
            if not image_tag:
                print(self.formatter.error(f"Unknown image variant: {variant}"))
                errors += 1
                continue

            # Identifier les containers utilisant actuellement cette image (avant pull)
            old_id = None
            affected_containers: List[str] = []
            try:
                old_img = self.manager.client.images.get(image_tag)
                old_id = old_img.short_id
                # Containers utilisant cette image (running ou stopped)
                all_containers = self.manager.client.containers.list(all=True)
                for c in all_containers:
                    if c.image.id == old_img.id and any("nihil" in (t or "") for t in (c.image.tags or [c.attrs.get("Config", {}).get("Image", "")])):
                        affected_containers.append(c.name)
            except Exception:
                pass

            print(self.formatter.info(f"Updating '{variant}' ({image_tag})..."))
            try:
                self.manager._pull_with_progress(image_tag)
                new_img = self.manager.client.images.get(image_tag)
                new_id = new_img.short_id
                if old_id and old_id == new_id:
                    print(self.formatter.info(f"'{variant}' is already up to date."))
                else:
                    print(self.formatter.success(f"'{variant}' updated successfully."))
                    # Si des containers utilisaient l'ancienne image, ils sont maintenant sur une image dangling
                    if affected_containers:
                        containers_to_upgrade.extend(affected_containers)
            except Exception as e:
                print(self.formatter.error(f"Failed to update '{variant}': {e}"))
                errors += 1

        # Avertir l'utilisateur si des containers ont perdu leur tag
        if containers_to_upgrade:
            print()
            print(self.formatter.warning(
                f"The following container(s) are still using the old image (now untagged): "
                f"{', '.join(containers_to_upgrade)}"
            ))
            print(self.formatter.warning(
                "Run 'nihil upgrade' to recreate them with the new image:"
            ))
            print(f"    nihil upgrade {' '.join(containers_to_upgrade)}")

        return 1 if errors > 0 else 0


    def _cmd_upgrade(self, args) -> int:
        """Met à jour l'image d'un ou plusieurs containers et les recrée à l'identique."""
        container_names: List[str] = getattr(args, "names", []) or []

        # Si aucun nom fourni → sélection interactive parmi les containers nihil
        if not container_names:
            from rich.prompt import Prompt
            nihil_containers = self.manager.list_containers(all=True)
            if not nihil_containers:
                print(self.formatter.warning("No nihil containers found."))
                return 0
            rows = []
            for c in nihil_containers:
                status = c.status.capitalize()
                try:
                    image_tag = c.image.tags[0] if c.image.tags else c.attrs["Config"]["Image"]
                except Exception:
                    image_tag = c.attrs.get("Config", {}).get("Image", "<deleted image>")
                rows.append([c.name, status, self.manager.short_image_name(image_tag)])
            print(self.formatter.section_header("NIHIL CONTAINERS", "🐳 "))
            self.formatter.print_table(["NAME", "STATUS", "IMAGE"], rows)
            selected: List[str] = []
            while True:
                available = [c.name for c in nihil_containers if c.name not in selected]
                if not available:
                    break
                try:
                    choice = Prompt.ask(
                        "[?] Select a container to upgrade",
                        choices=available,
                        default=available[0],
                    )
                    selected.append(choice)
                    remaining = [n for n in available if n != choice]
                    if not remaining:
                        break
                    more = Prompt.ask("[?] Add another container?", choices=["y", "n"], default="n")
                    if more != "y":
                        break
                except (KeyboardInterrupt, EOFError):
                    print("\nAborted.")
                    return 0
            if not selected:
                print("No container selected.")
                return 0
            container_names = selected

        errors = 0
        for container_name in container_names:
            print()
            print(self.formatter.section_header(f"UPGRADING '{container_name}'", "⬆️  "))

            # 1. Récupérer le container
            container = self.manager.get_container(container_name)
            if not container:
                print(self.formatter.error(f"Container '{container_name}' not found."))
                errors += 1
                continue

            # 2. Snapshot de la config
            snapshot = self.manager.snapshot_container_config(container)
            image_tag = snapshot["image"]
            
            # Normaliser vers latest pour nihil-images
            if "nihil-images" in image_tag and ":" in image_tag:
                repo = image_tag.split(":")[0]
                target_image = f"{repo}:latest"
            elif "nihil-images" in image_tag:
                target_image = f"{image_tag}:latest"
            else:
                target_image = image_tag

            requested_img = getattr(args, "image", None)
            if requested_img:
                target_image = self.manager.AVAILABLE_IMAGES.get(requested_img, target_image)

            snapshot["image"] = target_image

            print(self.formatter.info(f"Container image: {self.manager.short_image_name(image_tag)} ({image_tag})"))
            if target_image != image_tag:
                print(self.formatter.info(f"Targeting image: {target_image}"))

            # 3. Pull la nouvelle image
            old_id = None
            try:
                old_img = self.manager.client.images.get(image_tag)
                old_id = old_img.short_id
            except Exception:
                pass
            print(self.formatter.info("Pulling latest image..."))
            try:
                self.manager._pull_with_progress(target_image)
            except Exception as e:
                print(self.formatter.error(f"Failed to pull image '{target_image}': {e}"))
                errors += 1
                continue

            new_id = None
            try:
                new_img = self.manager.client.images.get(target_image)
                new_id = new_img.short_id
            except Exception:
                pass

            force_upgrade = getattr(args, "force", False)
            if old_id and old_id == new_id and image_tag == target_image and not force_upgrade:
                print(self.formatter.info("Image is already up to date. Skipping container recreation. Use --force to recreate anyway."))
                continue

            print(self.formatter.info("Backing up container specific files..."))
            paths_to_preserve = [
                "/root/.bash_history",
                "/root/.zsh_history",
                "/root/.python_history",
                "/root/.nxc",
                "/root/.cme",
                "/usr/share/responder/Responder.db",
                "/usr/share/responder/Responder.conf",
                "/root/.hashcat/hashcat.potfile",
                "/root/.john/john.pot",
                "/etc/hosts",
                "/etc/resolv.conf",
                "/opt/tools/Exegol-history/profile.sh",
                "/etc/proxychains.conf",
                "/etc/proxychains4.conf"
            ]
            saved_files = self.manager.extract_container_data(container, paths_to_preserve)

            # 4. Stopper + supprimer l'ancien container
            if container.status == "running":
                print(self.formatter.info(f"Stopping container '{container_name}'..."))
                self.manager.stop_container(container)
            print(self.formatter.info(f"Removing old container '{container_name}'..."))
            self.manager.remove_container(container, force=True)

            # 5. Recréer + démarrer le container
            print(self.formatter.info(f"Recreating container '{container_name}'..."))
            try:
                new_container = self.manager.recreate_container(snapshot)
                self.manager.start_container(new_container)
                
                if saved_files:
                    print(self.formatter.info("Restoring container specific files..."))
                    self.manager.restore_container_data(new_container, saved_files)

                print(self.formatter.success(
                    f"Container '{container_name}' upgraded and restarted successfully "
                    f"({old_id or '?'} → {new_id or '?'})."
                ))
            except Exception as e:
                print(self.formatter.error(f"Failed to recreate container '{container_name}': {e}"))
                errors += 1

        return 1 if errors > 0 else 0

    def _cmd_install(self, args) -> int:
        image_arg = args.image
        if image_arg is None:
            from rich.prompt import IntPrompt
            from rich.console import Console
            console = Console()
            print(self.formatter.info("Select an image to install/update:"))
            variants = list(self.manager.AVAILABLE_IMAGES.keys())
            rows = []
            for i, variant in enumerate(variants):
                rows.append([str(i+1), variant, self.manager.AVAILABLE_IMAGES[variant]])
            self.formatter.print_table(["#", "VARIANT", "IMAGE TAG"], rows)
            try:
                choice = IntPrompt.ask("Select number", choices=[str(k) for k in range(1, len(variants) + 1)], default=1)
                image_arg = variants[choice - 1]
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                return 0
        image_tag = self.manager.AVAILABLE_IMAGES.get(image_arg)
        if not image_tag:
            print(self.formatter.error(f"Unknown image variant: {image_arg}"))
            return 1
        print(self.formatter.info(f"Pulling image '{image_tag}'..."))
        try:
            self.manager._pull_with_progress(image_tag)
            print(self.formatter.success(f"Image '{image_tag}' installed/updated successfully."))
            return 0
        except Exception as e:
            print(self.formatter.error(f"Failed to pull image: {e}"))
            return 1

    def _cmd_uninstall(self, args) -> int:
        raw_images = args.names
        resolved_images = []
        if not raw_images:
            images_list = self.manager.list_images()
            if not images_list:
                print("No installed nihil images found.")
                return 0
            from rich.prompt import IntPrompt
            print(self.formatter.info("Select image(s) to uninstall:"))
            choices_map = []
            rows = []
            for i, img in enumerate(images_list):
                tags_raw = img.tags if img.tags else []
                short = ", ".join(self.manager.short_image_name(t) for t in tags_raw) or img.short_id
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                image_ref = img.tags[0] if img.tags else img.id
                choices_map.append(image_ref)
                rows.append([str(i+1), short, size])
            self.formatter.print_table(["#", "IMAGE", "SIZE"], rows)
            try:
                choice = IntPrompt.ask("Select an image number", choices=[str(k) for k in range(1, len(images_list) + 1)], default=1)
                selected_image = choices_map[choice - 1]
                resolved_images.append(selected_image)
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                return 0
        else:
            for item in raw_images:
                if item in self.manager.AVAILABLE_IMAGES:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES[item])
                elif item in ["nihil-ad", "nihil-ad:latest"]:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES.get("ad"))
                elif item in ["nihil", "nihil:latest"]:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES.get("full"))
                else:
                    resolved_images.append(item)
        images = resolved_images
        containers_to_remove = []
        for image in images:
            try:
                img_obj = self.manager.client.images.get(image)
                all_containers = self.manager.client.containers.list(all=True)
                for c in all_containers:
                    if c.image.id == img_obj.id:
                        containers_to_remove.append(c.name)
            except Exception:
                pass
        print(self.formatter.warning(f"Images to be removed: {', '.join(images)}"))
        if containers_to_remove:
            print(self.formatter.warning(f"The following containers are using these images:"))
            for container_name in containers_to_remove:
                print(f"  • {container_name}")
            print()
            try:
                remove_containers = input(self.formatter.info("Do you want to remove these containers too? [y/N] "))
            except EOFError:
                remove_containers = 'n'
            if remove_containers.lower() in ['y', 'yes']:
                print()
                for container_name in containers_to_remove:
                    try:
                        container = self.manager.get_container(container_name)
                        if container:
                            if container.status == "running":
                                print(self.formatter.info(f"Stopping container '{container_name}'..."))
                                self.manager.stop_container(container)
                            print(self.formatter.info(f"Removing container '{container_name}'..."))
                            self.manager.remove_container(container, force=True)
                            print(self.formatter.success(f"Container '{container_name}' removed successfully."))
                    except Exception as e:
                        print(self.formatter.error(f"Failed to remove container '{container_name}': {e}"), file=sys.stderr)
                print()
            else:
                print(self.formatter.error("Cannot remove images while containers are using them. Aborting."))
                return 1
        if args.force:
            print(self.formatter.warning("--force flag is set (not needed if containers were removed)"))
        try:
            confirm = input(self.formatter.info("Proceed with image removal? [y/N] "))
        except EOFError:
            confirm = 'n'
        if confirm.lower() not in ['y', 'yes']:
            print("Aborted.")
            return 0
        errors = 0
        for image in images:
            print(self.formatter.info(f"Removing image '{image}'..."))
            try:
                self.manager.remove_image(image, force=args.force)
                print(self.formatter.success(f"Image '{image}' removed successfully."))
            except Exception as e:
                print(self.formatter.error(str(e)), file=sys.stderr)
                errors += 1
        return 1 if errors > 0 else 0

    def _cmd_tools(self, args) -> int:
        from nihil.features.images import AVAILABLE_IMAGES
        image_key = args.image or "full"
        if image_key == "active-directory":
            image_key = "ad"
        image_tag = AVAILABLE_IMAGES.get(image_key)
        if not image_tag:
            print(self.formatter.error(f"Unknown image variant: {image_key}"), file=sys.stderr)
            return 1

        short_name = self.manager.short_image_name(image_tag)
        print(self.formatter.info(f"Reading tools manifest from {short_name} ({image_tag})..."))

        manifest = self.manager.get_tools_manifest(image_tag)
        if not manifest:
            print(self.formatter.error("Could not read tools.json from image. Is the image installed?"), file=sys.stderr)
            return 1

        category_filter = getattr(args, "category", None)
        total = 0

        for category, tools in manifest.items():
            if category_filter and category != category_filter:
                continue
            if not tools:
                continue

            print()
            print(self.formatter.section_header(category.upper().replace("_", " "), ""))
            rows = []
            for tool in tools:
                rows.append([tool["name"], tool.get("cmd") or "-", tool.get("description", "")])
                total += 1
            self.formatter.print_table(["TOOL", "COMMAND", "DESCRIPTION"], rows)

        print()
        print(self.formatter.info(f"{total} tools available in {short_name}"))
        return 0

    def _cmd_images(self) -> int:
        print(self.formatter.section_header("AVAILABLE IMAGE VARIANTS"))
        rows = []
        variant_descriptions = {
            "full": "The whole flock, every tool, every module",
            "ad": "Nest in their Active Directory",
            "web": "Beak through their web apps",
            "ctf": "Capture the flag, no fluff",
        }
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            description = variant_descriptions.get(variant, "Specialized image")
            info = self.manager.get_image_info(image_url)
            size_str = f"{info['size_bytes'] / (1024**3):.2f} GB" if info else "-"
            rows.append([variant, self.manager.short_image_name(image_url), size_str, description])
        self.formatter.print_table(["VARIANT", "IMAGE", "SIZE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Usage: nihil start <name> --image <variant>"))
        return 0

    def _cmd_info(self, args) -> int:
        container_name = getattr(args, "container", None)
        if container_name:
            self.manager = self.manager or NihilManager()
            container = self.manager.get_container(container_name)
            if not container:
                print(self.formatter.error(f"Container '{container_name}' doesn't exist."), file=sys.stderr)
                return 1
            self._print_container_info(container, args, created=False)
            return 0
        print(self.formatter.info(f"Nihil version {__version__}\n"))
        variant_descriptions = {
            "full": "The whole flock, every tool, every module",
            "ad": "Nest in their Active Directory",
            "web": "Beak through their web apps",
            "ctf": "Capture the flag, no fluff",
        }
        print(self.formatter.section_header("AVAILABLE IMAGE VARIANTS"))
        rows = []
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            description = variant_descriptions.get(variant, "Specialized image")
            info = self.manager.get_image_info(image_url)
            size_str = f"{info['size_bytes'] / (1024**3):.2f} GB" if info else "-"
            rows.append([variant, self.manager.short_image_name(image_url), size_str, description])
        self.formatter.print_table(["VARIANT", "IMAGE", "SIZE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Use 'nihil start <name> --image <variant>' to create a container with a specific image."))
        print()
        print(self.formatter.section_header("INSTALLED IMAGES"))
        images = self.manager.list_images()
        if images:
            rows = []
            for img in images:
                tags = img.tags if img.tags else []
                short = ", ".join(self.manager.short_image_name(t) for t in tags) or img.short_id
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                rows.append([short, size])
            self.formatter.print_table(["IMAGE", "SIZE"], rows, [50, 12])
        else:
            print("  No nihil images installed locally.")
            print("  Use 'nihil start <name> --image <variant>' to pull and use an image.")
        print(self.formatter.section_header("CONTAINERS", "🐳"))
        containers = self.manager.list_containers()
        if containers:
            rows = []
            for c in containers:
                name = c.name
                status_raw = c.status
                if status_raw == "running":
                    status = ("Running", self.formatter.GREEN)
                elif status_raw == "exited":
                    status = ("Stopped", self.formatter.RED)
                else:
                    status = (f"{status_raw}", self.formatter.YELLOW)
                try:
                    image_raw = c.image.tags[0] if c.image.tags else c.attrs.get('Config', {}).get('Image', '<none>')
                except Exception:
                    image_raw = c.attrs.get('Config', {}).get('Image', '<deleted image>')
                if "/" in image_raw:
                    image = image_raw.split("/")[-1]
                    if image.startswith("nihil-images"):
                        image = image.replace("nihil-images-", "", 1).replace("nihil-images", "full", 1)
                else:
                    image = image_raw
                is_privileged = c.attrs['HostConfig']['Privileged']
                config = ("Privileged 💥", self.formatter.RED) if is_privileged else "Standard"
                rows.append([name, status, image, config])
            def get_text_length(cell):
                if isinstance(cell, tuple):
                    return len(str(cell[0]))
                return len(str(cell))
            name_width = max(len("NAME"), max(get_text_length(row[0]) for row in rows)) + 2
            status_width = max(len("STATUS"), max(get_text_length(row[1]) for row in rows)) + 2
            image_width = max(len("IMAGE"), max(get_text_length(row[2]) for row in rows)) + 2
            config_width = max(len("CONFIG"), max(get_text_length(row[3]) for row in rows)) + 2
            self.formatter.print_table(["NAME", "STATUS", "IMAGE", "CONFIG"], rows, [name_width, status_width, image_width, config_width])
        else:
            print("  No nihil containers found.")
        return 0

    def _cmd_config(self, args) -> int:
        from nihil.config import CONFIG_FILE
        if getattr(args, "edit", False):
            import shutil
            import subprocess
            editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi") or "vi"
            subprocess.run([editor, str(CONFIG_FILE)])
            return 0
        # Affichage de la config courante
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            console = Console()
            cfg = self.config
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="bold cyan")
            table.add_column(style="white")
            table.add_row("Config file", str(CONFIG_FILE))
            table.add_row("", "")
            table.add_row("[bold]network.default_network[/]", cfg.default_network)
            table.add_row("[bold]workspace.default_path[/]", str(cfg.default_workspace) if cfg.default_workspace else "[dim]none[/]")
            table.add_row("[bold]shell.default_shell[/]", cfg.default_shell)
            table.add_row("[bold]shell.logging.always_enable[/]", "[green]yes[/]" if cfg.logging_always_enable else "[red]no[/]")
            table.add_row("[bold]shell.logging.method[/]", cfg.logging_method)
            table.add_row("[bold]my_resources.enabled[/]", "[green]yes[/]" if cfg.my_resources_enabled else "[red]no[/]")
            table.add_row("[bold]my_resources.path[/]", str(cfg.my_resources_path))
            table.add_row("[bold]display.x11_by_default[/]", "[green]yes[/]" if cfg.x11_by_default else "[red]no[/]")
            table.add_row("[bold]updates.auto_check[/]", "[green]yes[/]" if cfg.auto_check_updates else "[red]no[/]")
            console.print(Panel(table, title="[bold]Nihil Configuration[/]", border_style="blue", padding=(0, 1)))
            print(self.formatter.info(f"Edit: nihil config --edit  or  $EDITOR {CONFIG_FILE}"))
        except ImportError:
            print(f"Config file: {CONFIG_FILE}")
        return 0

    def _cmd_completion(self, args) -> int:
        import shutil
        import subprocess
        shell = args.shell
        tool = shutil.which("register-python-argcomplete")
        if not tool:
            print(
                self.formatter.error(
                    "register-python-argcomplete n'est pas disponible dans le PATH.\n"
                    "Installez argcomplete dans le même environnement que Nihil, "
                    "puis réessayez."
                ),
                file=sys.stderr,
            )
            return 1
        cmd = [tool]
        if shell == "zsh":
            cmd.extend(["--shell", "zsh"])
        cmd.append("nihil")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout, end="")
            return 0
        except subprocess.CalledProcessError as e:
            print(self.formatter.error(f"Échec de la génération du script de complétion pour {shell} : {e}"), file=sys.stderr)
            return 1


def main() -> int:
    argv: List[str] = sys.argv[1:]
    exit_code: int
    try:
        controller = NihilController()
        exit_code = controller.run(argv)
    except KeyboardInterrupt:
        formatter = NihilFormatter()
        print(f"\n\n{formatter.warning('User interruption.')}")
        exit_code = 130
    except NihilError as e:
        formatter = NihilFormatter()
        print(formatter.error(str(e)), file=sys.stderr)
        exit_code = e.exit_code
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        exit_code = 1
    try:
        log_command(argv, exit_code)
    except Exception:
        pass
    return exit_code
