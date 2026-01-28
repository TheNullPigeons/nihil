#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Controller - Orchestrates command execution"""

import sys
from typing import Optional, List

from nihil.nihilManager import NihilManager
from nihil.nihilHelp import create_parser
from nihil.nihilFormatter import NihilFormatter
from nihil.nihilError import NihilError
from nihil import __version__
from nihil.nihilDoctor import NihilDoctor
from nihil.nihilHistory import log_command
from nihil.nihilBanner import print_compact_banner


class NihilController:
    """Orchestrates command execution"""
    
    def __init__(self):
        self.parser = create_parser()
        self.manager = None
        self.formatter = NihilFormatter()
    
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
            return self._cmd_info()
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
        
        if container:
            print(self.formatter.info(f"Container '{container_name}' found."))
            if container.status == "running":
                print(self.formatter.warning(f"Container '{container_name}' is already running."))
            else:
                print(self.formatter.info(f"Starting container '{container_name}'..."))
                self.manager.start_container(container)
                print(self.formatter.success(f"Container '{container_name}' started successfully."))
        else:
            print(self.formatter.info(f"Container '{container_name}' doesn't exist. Creating..."))
            network_map = {
                "host": "host",
                "disabled": "none",
                "docker": "bridge",
                "nat": "bridge"
            }
            image = self.manager.AVAILABLE_IMAGES.get(args.image, self.manager.DEFAULT_IMAGE)
            print(self.formatter.info(f"Using image variant: {args.image} ({image})"))
            
            container = self.manager.create_container(
                name=container_name,
                image=image,
                privileged=args.privileged,
                network_mode=network_map.get(args.network, "host"),
                workspace=args.workspace
            )
            print(self.formatter.info(f"Container '{container_name}' created."))
            print(self.formatter.info(f"Starting container '{container_name}'..."))
            self.manager.start_container(container)
            print(self.formatter.success(f"Container '{container_name}' created and started successfully."))
        
        if not args.no_shell:
            command = "zsh"
            if args.log:
                import datetime
                timestamp = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                logfile = f"/workspace/logs/{timestamp}_shell.asciinema"
                title = f"Nihil Session {timestamp}"
                self.manager.exec_in_container(container, "mkdir -p /workspace/logs")
                print(self.formatter.info(f"Logging session to {logfile}"))
                command = f"asciinema rec -i 2 --stdin --quiet --command zsh --title '{title}' {logfile}"
            
            print(self.formatter.info(f"Connecting to container '{container_name}'..."))
            self.manager.exec_in_container(container, command)
        
        return 0
    
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
    
    def _cmd_uninstall(self, args) -> int:
        """Remove nihil images"""
        images = args.names
        if not images:
            images = [self.manager.DEFAULT_IMAGE]
        
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
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            if variant == "active-directory":
                continue
            description = "Base image (OS + core tools)" if variant == "base" else "Active Directory tools (base + AD tools)"
            rows.append([variant, image_url, description])
        
        self.formatter.print_table(["VARIANT", "IMAGE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Usage: nihil start <name> --image <variant>"))
        return 0
    
    def _cmd_info(self) -> int:
        """Display information about images and containers"""
        print(self.formatter.info(f"Nihil version {__version__}\n"))
        
        print(self.formatter.section_header("AVAILABLE IMAGE VARIANTS", "📦 "))
        rows = []
        for variant, image_url in self.manager.AVAILABLE_IMAGES.items():
            if variant == "active-directory":
                continue
            description = "Base image (OS + core tools)" if variant == "base" else "Active Directory tools (base + AD tools)"
            rows.append([variant, image_url, description])
        
        self.formatter.print_table(["VARIANT", "IMAGE", "DESCRIPTION"], rows)
        print()
        print(self.formatter.info("Use 'nihil start <name> --image <variant>' to create a container with a specific image."))
        print()
        
        print(self.formatter.section_header("INSTALLED IMAGES", "🖼️ "))
        images = self.manager.list_images()
        if images:
            rows = []
            for img in images:
                tags = ", ".join(img.tags) if img.tags else "<none>"
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                rows.append([tags, size])
            
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
                config = ("Privileged", self.formatter.RED) if is_privileged else "Standard"
                
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
