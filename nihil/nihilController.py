#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Controller - Orchestrates command execution"""

import sys
from typing import Optional, List

from nihil.nihilManager import NihilManager, ensure_filesystem
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
        ensure_filesystem()
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
                    elif "pwn" in variant or "crypto" in variant:
                        desc = "Pwn & Crypto tools"
                    
                    rows.append([str(i+1), variant, desc])
                
                self.formatter.print_table(["#", "VARIANT", "DESCRIPTION"], rows)
                
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
            # Force pull to update
            self.manager.client.images.pull(image_tag)
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
                tags = ", ".join(img.tags) if img.tags else "<none>"
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                # Keep track of full image ID or tag for removal
                image_ref = img.tags[0] if img.tags else img.id
                choices_map.append(image_ref)
                rows.append([str(i+1), tags, size])
            
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
