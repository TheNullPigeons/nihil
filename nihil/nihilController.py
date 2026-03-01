#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Controller - Orchestrates command execution"""

import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path
from typing import Optional, List
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from nihil.nihilManager import NihilManager, ensure_filesystem
from nihil.nihilHelp import create_parser
from nihil.nihilFormatter import NihilFormatter
from nihil.nihilError import NihilError
from nihil import __version__
from nihil.nihilDoctor import NihilDoctor
from nihil.nihilHistory import log_command
from nihil.nihilBanner import print_compact_banner


BROWSER_UI_PASSWORDS_FILE = Path.home() / ".nihil" / "browser_ui_passwords.json"


class NihilController:
    """Orchestrates command execution"""
    
    def __init__(self):
        ensure_filesystem()
        self.parser = create_parser()
        self.manager = None
        self.formatter = NihilFormatter()

    def _save_browser_ui_password(self, container_name: str, password: str) -> None:
        """Persist generated Browser UI password (wrapper-generated only)."""
        path = BROWSER_UI_PASSWORDS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        data[container_name] = password
        path.write_text(json.dumps(data, indent=0))
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _load_browser_ui_password(self, container_name: str) -> Optional[str]:
        """Return stored Browser UI password for container, or None."""
        path = BROWSER_UI_PASSWORDS_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return data.get(container_name)
        except (json.JSONDecodeError, OSError):
            return None

    def _clear_browser_ui_password(self, container_name: str) -> None:
        """Remove stored Browser UI password when container is removed."""
        path = BROWSER_UI_PASSWORDS_FILE
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            data.pop(container_name, None)
            if data:
                path.write_text(json.dumps(data, indent=0))
            else:
                path.unlink()
        except (json.JSONDecodeError, OSError):
            pass

    def _get_session_str_for_recap(self, container, container_name: str) -> Optional[str]:
        """Return 'root:password' or 'root:***' for recap; None if unknown."""
        pwd = self._load_browser_ui_password(container_name)
        if pwd:
            return f"root:{pwd}"
        env_list = container.attrs.get("Config", {}).get("Env") or []
        if any(e.startswith("NIHIL_BROWSER_UI_PASSWORD=") for e in env_list):
            return "root:***"
        return None

    @staticmethod
    def _is_browser_ui_ready(port: int) -> bool:
        """True if the Browser UI page is served (HTTP 200 + page content)."""
        try:
            req = Request(f"http://127.0.0.1:{port}/", headers={"User-Agent": "Nihil-Wrapper"})
            with urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    return False
                body = resp.read().decode("utf-8", errors="ignore")
                return "Nihil" in body
        except (URLError, HTTPError, OSError, ValueError):
            return False

    def run(self, args: Optional[list] = None) -> int:
        """Run the controller with parsed arguments"""
        parsed_args = self.parser.parse_args(args)
        
        should_show_banner = (
            parsed_args.command is not None and
            parsed_args.command not in ["version", "completion"]
        )
        
        if should_show_banner:
            print_compact_banner()
            print()
        
        if parsed_args.command is None:
            self.parser.print_help()
            return 0
        
        if parsed_args.command == "version":
            print(f"Nihil version {__version__}")
            return 0

        if parsed_args.command == "doctor":
            doctor = NihilDoctor(formatter=self.formatter)
            return doctor.run()
        
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
        elif parsed_args.command == "install":
            return self._cmd_install(parsed_args)
        elif parsed_args.command == "uninstall":
            return self._cmd_uninstall(parsed_args)
        elif parsed_args.command == "completion":
            return self._cmd_completion(parsed_args)
        
        return 0
    
    def _cmd_start(self, args) -> int:
        """Start a container (creates it if it doesn't exist)"""
        container_name = args.name
        
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
            # Retarder l'affichage des infos si Browser UI : on les affichera avec Session (login:mdp) après préparation
            env_list = container.attrs.get("Config", {}).get("Env") or []
            delay_info = not args.no_shell and any(e == "NIHIL_BROWSER_UI=1" for e in env_list)
            if not delay_info:
                self._print_container_info(container, args, created=False)
        else:
            print(self.formatter.info(f"Container '{container_name}' doesn't exist. Creating..."))
            network_map = {
                "host": "host",
                "disabled": "none",
                "docker": "bridge",
                "nat": "bridge"
            }
            
            # Determine image variant
            image_arg = args.image
            if image_arg is None:
                # Interactive selection using Rich
                from rich.console import Console
                from rich.prompt import IntPrompt
                
                console = Console()
                print(self.formatter.info("No image specified. Please select one:"))
                
                variants = [v for v in self.manager.AVAILABLE_IMAGES.keys() if v != "active-directory"]
                # Ensure specific order if desired, or sort it
                # variants.sort()
                
                rows = []
                for i, variant in enumerate(variants):
                    # Simple descriptions mapping
                    desc = "Base image"
                    if "ad" in variant or "active-directory" in variant:
                        desc = "Active Directory tools"
                    elif "web" in variant:
                        desc = "Web Hacking tools"
                    
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
                
                self.formatter.print_table(
                    ["#", "VARIANT", "DESCRIPTION", "SIZE", "INSTALLED"], rows
                )
                
                choices_indices = list(range(1, len(variants) + 1))
                try:
                    choice = IntPrompt.ask(
                        "Select an image", 
                        choices=[str(c) for c in choices_indices],
                        default=1
                    )
                    image_arg = variants[choice - 1]
                except KeyboardInterrupt:
                    print("\nAborted.")
                    return 1
            
            image = self.manager.AVAILABLE_IMAGES.get(image_arg, self.manager.DEFAULT_IMAGE)
            print(self.formatter.info(f"Using image variant: {image_arg} ({image})"))
            
            vpn_path = getattr(args, "vpn", None)
            # Workspace selection: explicit --workspace wins, otherwise --workspace-here uses current directory.
            workspace_path = args.workspace
            if workspace_path is None and getattr(args, "workspace_here", False):
                workspace_path = os.getcwd()
            # Docker requires an absolute host path for bind mounts.
            if workspace_path is not None:
                workspace_path = str(Path(workspace_path).expanduser().resolve())

            browser_ui_enabled = getattr(args, "browser_ui", False)
            browser_ui_port = getattr(args, "browser_ui_port", None)
            browser_ui_password = getattr(args, "browser_ui_password", None)
            # Wrapper génère le mdp et l'injecte : le script container utilise NIHIL_BROWSER_UI_PASSWORD
            if browser_ui_enabled and browser_ui_password is None:
                browser_ui_password = secrets.token_urlsafe(12)
                self._save_browser_ui_password(container_name, browser_ui_password)

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
                 browser_ui=browser_ui_enabled,
                 browser_ui_port=browser_ui_port if browser_ui_enabled else None,
                 browser_ui_password=browser_ui_password if browser_ui_enabled else None,
            )
            print(self.formatter.info(f"Container '{container_name}' created."))
            print(self.formatter.info(f"Starting container '{container_name}'..."))
            self.manager.start_container(container)
            print(self.formatter.success(f"Container '{container_name}' created and started successfully."))
            # Retarder l'affichage des infos si Browser UI : on les affichera avec Session (login:mdp) après préparation
            if not (browser_ui_enabled and not args.no_shell):
                self._print_container_info(container, args, created=True)
        
        if not args.no_shell:
            command = "zsh"
            # Existing container + --vpn: copy .ovpn into container and run VPN for this session only; VPN stops when shell exits
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
                            # Run OpenVPN quietly for this session only; all output goes to /dev/null
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

            # Si Browser UI est activé, attendre que le port noVNC écoute avant d'ouvrir le shell
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
                    if self._is_browser_ui_ready(browser_ui_port):
                        print(self.formatter.success("Browser UI ready."))
                        break
                    time.sleep(2)
                else:
                    print(self.formatter.warning("Browser UI may still be starting; open the link from the recap when ready."))
                # Session (login:mdp) vient du wrapper (fichier local), pas lu depuis le container
                session_str = self._get_session_str_for_recap(container, container_name)
                self._print_container_info(
                    container, args, created=not container_existed, browser_ui_session=session_str
                )

            print(self.formatter.info(f"Connecting to container '{container_name}'..."))
            self.manager.exec_in_container(container, command)
        
        return 0

    def _print_container_info(
        self, container, args, created: bool = False, browser_ui_session: Optional[str] = None
    ) -> None:
        """Print container summary (name, image, network, privileged, workspace) like Exegol."""
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
        # Build colored displays
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

        # VPN display: created containers with NIHIL_VPN=1 vs session-only VPN on existing containers.
        # For existing containers started with --vpn but without /dev/net/tun, show as disabled.
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

        # X11 display: show whether X11/XWayland integration is active.
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

        # Browser UI (noVNC) display.
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
        title = "New container" if created else "Container"
        Console().print(Panel(table, title=f"[bold]{title}[/]", border_style="blue", padding=(0, 1)))

    def _cmd_stop(self, args) -> int:
        """Stop a container"""
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
        """Remove one or more containers"""
        container_names = args.names
        
        if not container_names:
            # Interactive selection loop
            from rich.prompt import Prompt
            from rich.console import Console
            
            console = Console()
            nihil_containers = self.manager.list_containers(all=True)
            
            if not nihil_containers:
                print("No nihil containers found.")
                return 0
                
            selected_containers = []
            
            while True:
                # Refresh list (excluding already selected)
                available_containers = [c for c in nihil_containers if c.name not in selected_containers]
                
                if not available_containers:
                    break
                    
                rows = []
                for c in available_containers:
                    status = c.status.capitalize()
                    image_tag = c.image.tags[0] if c.image.tags else c.attrs['Config']['Image']
                    # Simplify image tag display
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
                    choice = Prompt.ask(
                        f"[?] Select a container by its name", 
                        choices=[c.name for c in available_containers],
                        default=default_choice
                    )
                    selected_containers.append(choice)
                    
                    if not [c for c in available_containers if c.name != choice]:
                         # No more containers left to select
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
            self._clear_browser_ui_password(container_name)
            print(self.formatter.success(f"Container '{container_name}' removed successfully."))
        
        return 1 if errors > 0 else 0
    
    def _cmd_exec(self, args) -> int:
        """Execute a command in a container"""
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

    def _cmd_install(self, args) -> int:
        """Install or update nihil images"""
        image_arg = args.image
        
        if image_arg is None:
            # Interactive selection
            from rich.prompt import IntPrompt
            from rich.console import Console
            
            console = Console()
            print(self.formatter.info("Select an image to install/update:"))
            
            variants = [v for v in self.manager.AVAILABLE_IMAGES.keys() if v != "active-directory"]
            rows = []
            for i, variant in enumerate(variants):
                rows.append([str(i+1), variant, self.manager.AVAILABLE_IMAGES[variant]])
            
            self.formatter.print_table(["#", "VARIANT", "IMAGE TAG"], rows)
            
            try:
                choice = IntPrompt.ask(
                    "Select number", 
                    choices=[str(k) for k in range(1, len(variants) + 1)],
                    default=1
                )
                image_arg = variants[choice - 1]
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                return 0
        
        # Resolve full image tag
        image_tag = self.manager.AVAILABLE_IMAGES.get(image_arg)
        if not image_tag:
            print(self.formatter.error(f"Unknown image variant: {image_arg}"))
            return 1

        print(self.formatter.info(f"Pulling image '{image_tag}'..."))
        try:
            # Force pull to update, with progress display
            self.manager._pull_with_progress(image_tag)
            print(self.formatter.success(f"Image '{image_tag}' installed/updated successfully."))
            return 0
        except Exception as e:
            print(self.formatter.error(f"Failed to pull image: {e}"))
            return 1

    
    def _cmd_uninstall(self, args) -> int:
        """Remove nihil images"""
        raw_images = args.names
        resolved_images = []
        
        if not raw_images:
            # Interactive selection if no argument provided
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
                choice = IntPrompt.ask(
                    "Select an image number", 
                    choices=[str(k) for k in range(1, len(images_list) + 1)],
                    default=1
                )
                selected_image = choices_map[choice - 1]
                resolved_images.append(selected_image)
            except (KeyboardInterrupt, EOFError):
                 print("\nAborted.")
                 return 0
                 
        else:
            for item in raw_images:
                # 1. Check if it's a known available image key (base, ad, etc.)
                if item in self.manager.AVAILABLE_IMAGES:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES[item])
                # 2. Check for the display name "nihil-ad" or "nihil-ad:latest" (shown in nihil info)
                elif item in ["nihil-ad", "nihil-ad:latest"]:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES.get("ad"))
                # 3. Handle base image display name "nihil", "nihil:latest"
                elif item in ["nihil", "nihil:latest"]:
                    resolved_images.append(self.manager.AVAILABLE_IMAGES.get("base"))
                # 4. Fallback to raw input
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
    
    def _cmd_images(self) -> int:
        """List available image variants"""
        print(self.formatter.section_header("AVAILABLE IMAGE VARIANTS", "📦 "))
        rows = []
        variant_descriptions = {
            "base": "Base image (OS + core tools)",
            "ad": "Active Directory tools (base + AD tools)",
            "web": "Web / HTTP tools (base + web tools)",
        }
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            if variant == "active-directory":
                continue
            description = variant_descriptions.get(variant, "Specialized image")
            rows.append([variant, self.manager.short_image_name(image_url), description])
        
        self.formatter.print_table(["VARIANT", "IMAGE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Usage: nihil start <name> --image <variant>"))
        return 0
    
    def _cmd_info(self, args) -> int:
        """Display information about images and containers, or a specific container."""
        # If a specific container is requested, show the detailed panel and exit.
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
            "base": "Base image (OS + core tools)",
            "ad": "Active Directory tools (base + AD tools)",
            "web": "Web / HTTP tools (base + web tools)",
        }
        print(self.formatter.section_header("AVAILABLE IMAGE VARIANTS", "📦 "))
        rows = []
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            if variant == "active-directory":
                continue
            description = variant_descriptions.get(variant, "Specialized image")
            rows.append([variant, self.manager.short_image_name(image_url), description])
        
        self.formatter.print_table(["VARIANT", "IMAGE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Use 'nihil start <name> --image <variant>' to create a container with a specific image."))
        print()
        
        print(self.formatter.section_header("INSTALLED IMAGES", "🖼️ "))
        images = self.manager.list_images()
        if images:
            rows = []
            for img in images:
                tags = img.tags if img.tags else []
                # Show compact name for each tag, fallback to image short id
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
                
                image_raw = c.image.tags[0] if c.image.tags else "<none>"
                if "/" in image_raw:
                    image = image_raw.split("/")[-1]
                    if image.startswith("nihil-images"):
                        image = image.replace("nihil-images", "nihil", 1)
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
            
            self.formatter.print_table(
                ["NAME", "STATUS", "IMAGE", "CONFIG"], 
                rows,
                [name_width, status_width, image_width, config_width]
            )
        else:
            print("  No nihil containers found.")
        
        return 0

    def _cmd_completion(self, args) -> int:
        """Generate shell completion script (bash or zsh)."""
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
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            print(result.stdout, end="")
            return 0
        except subprocess.CalledProcessError as e:
            print(
                self.formatter.error(
                    f"Échec de la génération du script de complétion pour {shell} : {e}"
                ),
                file=sys.stderr,
            )
            return 1


def main() -> int:
    """Main entry point with command history logging."""
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
