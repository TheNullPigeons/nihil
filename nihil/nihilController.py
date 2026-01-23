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


class NihilController:
    """Orchestrates command execution"""
    
    def __init__(self):
        self.parser = create_parser()
        self.manager = None
        self.formatter = NihilFormatter()
    
    def run(self, args: Optional[list] = None) -> int:
        """Run the controller with parsed arguments"""
        parsed_args = self.parser.parse_args(args)
        
        if parsed_args.command is None:
            self.parser.print_help()
            return 0
        
        if parsed_args.command == "version":
            print(f"Nihil version {__version__}")
            return 0

        if parsed_args.command == "doctor":
            doctor = NihilDoctor(formatter=self.formatter)
            return doctor.run()
        
        # Initialize Docker manager for commands that need it
        try:
            self.manager = NihilManager()
        except NihilError as e:
            print(self.formatter.error(str(e)), file=sys.stderr)
            return e.exit_code
        
        if parsed_args.command == "info":
            return self._cmd_info()
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
            container = self.manager.create_container(
                name=container_name,
                privileged=args.privileged,
                network_mode=args.network if args.network else None,
                workspace=args.workspace
            )
            print(self.formatter.info(f"Container '{container_name}' created."))
            print(self.formatter.info(f"Starting container '{container_name}'..."))
            self.manager.start_container(container)
            print(self.formatter.success(f"Container '{container_name}' created and started successfully."))
        
        # Connect to container if requested
        if not args.no_shell:
            print(self.formatter.info(f"Connecting to container '{container_name}'..."))
            self.manager.exec_in_container(container, "bash")
        
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
            
            # Stop container if running
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
        
        # Check which containers are using these images
        containers_to_remove = []
        for image in images:
            try:
                img_obj = self.manager.client.images.get(image)
                # Find containers using this image
                all_containers = self.manager.client.containers.list(all=True)
                for c in all_containers:
                    if c.image.id == img_obj.id:
                        containers_to_remove.append(c.name)
            except Exception:
                pass  # Image might not exist, will be handled later
        
        # Display what will be removed
        print(self.formatter.warning(f"Images to be removed: {', '.join(images)}"))
        
        if containers_to_remove:
            print(self.formatter.warning(f"The following containers are using these images:"))
            for container_name in containers_to_remove:
                print(f"  • {container_name}")
            print()
            
            # Ask if user wants to remove containers too
            try:
                remove_containers = input(self.formatter.info("Do you want to remove these containers too? [y/N] "))
            except EOFError:
                remove_containers = 'n'
            
            if remove_containers.lower() in ['y', 'yes']:
                # Remove containers first
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
        
        # Final confirmation for image removal
        if args.force:
            print(self.formatter.warning("--force flag is set (not needed if containers were removed)"))
        
        try:
            confirm = input(self.formatter.info("Proceed with image removal? [y/N] "))
        except EOFError:
            confirm = 'n'
        
        if confirm.lower() not in ['y', 'yes']:
            print("Aborted.")
            return 0
        
        # Remove images
        errors = 0
        for image in images:
            print(self.formatter.info(f"Removing image '{image}'..."))
            try:
                self.manager.remove_image(image, force=args.force)
                print(self.formatter.success(f"Image '{image}' removed successfully."))
            except Exception as e: 
                # Catching broadly to print error via formatter
                print(self.formatter.error(str(e)), file=sys.stderr)
                errors += 1
        
        return 1 if errors > 0 else 0
    
    def _cmd_info(self) -> int:
        """Display information about images and containers"""
        print(self.formatter.info(f"Nihil version {__version__}\n"))
        
        # Images
        print(self.formatter.section_header("Available images", "🖼️"))
        images = self.manager.list_images()
        if images:
            for img in images:
                tags = ", ".join(img.tags) if img.tags else "<none>"
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                print(self.formatter.table_row([tags, size], [30, 10]))
        else:
            print("  No nihil images found.")
        
        # Containers
        print(self.formatter.section_header("Containers", "🐳"))
        containers = self.manager.list_containers()
        if containers:
            for c in containers:
                name = c.name
                status = c.status
                image = c.image.tags[0] if c.image.tags else "<none>"
                config = "Privileged: On 🔥" if c.attrs['HostConfig']['Privileged'] else "Standard"
                print(self.formatter.table_row([name, f"[{status}]", image, config], [20, 12, 15, 20]))
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

        # Construction de la commande en fonction du shell
        cmd = [tool]
        if shell == "zsh":
            # argcomplete sait générer un snippet adapté à zsh
            cmd.extend(["--shell", "zsh"])
        cmd.append("nihil")

        try:
            # On imprime le script sur stdout pour permettre :
            #   nihil completion bash | sudo tee /etc/bash_completion.d/nihil
            #   nihil completion zsh  > ~/.zfunc/_nihil  (par ex.)
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

    # Always try to log history, but never fail the CLI if this breaks
    try:
        log_command(argv, exit_code)
    except Exception:
        pass

    return exit_code
