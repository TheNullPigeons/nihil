#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nihil Controller - Orchestrates command execution"""

import sys
from typing import Optional
from nihil.nihilManager import NihilManager
from nihil.nihilHelp import create_parser
from nihil.nihilFormatter import NihilFormatter
from nihil import __version__


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
        
        # Initialize Docker manager for commands that need it
        try:
            self.manager = NihilManager()
        except SystemExit:
            return 1
        
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
                if self.manager.start_container(container):
                    print(self.formatter.success(f"Container '{container_name}' started successfully."))
                else:
                    return 1
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
            if self.manager.start_container(container):
                print(self.formatter.success(f"Container '{container_name}' created and started successfully."))
            else:
                return 1
        
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
            print(f"Error: Container '{container_name}' doesn't exist.", file=sys.stderr)
            return 1
        
        if container.status != "running":
            print(f"[!] Container '{container_name}' is not running.")
            return 0
        
        print(f"[*] Stopping container '{container_name}'...")
        if self.manager.stop_container(container):
            print(f"[✓] Container '{container_name}' stopped successfully.")
            return 0
        return 1
    
    def _cmd_remove(self, args) -> int:
        """Remove one or more containers"""
        container_names = args.names
        errors = 0
        
        for container_name in container_names:
            container = self.manager.get_container(container_name)
            if not container:
                print(f"Error: Container '{container_name}' doesn't exist.", file=sys.stderr)
                errors += 1
                continue
            
            # Stop container if running
            if container.status == "running":
                print(f"[*] Stopping container '{container_name}'...")
                self.manager.stop_container(container)
            
            print(f"[*] Removing container '{container_name}'...")
            if self.manager.remove_container(container, force=args.force):
                print(f"[✓] Container '{container_name}' removed successfully.")
            else:
                errors += 1
        
        return 1 if errors > 0 else 0
    
    def _cmd_exec(self, args) -> int:
        """Execute a command in a container"""
        container_name = args.name
        
        container = self.manager.get_container(container_name)
        if not container:
            print(f"Error: Container '{container_name}' doesn't exist.", file=sys.stderr)
            return 1
        
        if container.status != "running":
            print(f"Error: Container '{container_name}' is not running.", file=sys.stderr)
            return 1
        
        command = " ".join(args.command) if args.command else "bash"
        self.manager.exec_in_container(container, command)
        return 0
    
    def _cmd_info(self) -> int:
        """Display information about images and containers"""
        print(f"[*] Nihil version {__version__}\n")
        
        # Images
        print("🖼️  Available images")
        print("─" * 60)
        images = self.manager.list_images()
        if images:
            for img in images:
                tags = ", ".join(img.tags) if img.tags else "<none>"
                size = f"{img.attrs['Size'] / (1024**3):.2f} GB"
                print(f"  • {tags:30} {size:>10}")
        else:
            print("  No nihil images found.")
        
        print()
        
        # Containers
        print("🐳 Containers")
        print("─" * 60)
        containers = self.manager.list_containers()
        if containers:
            for c in containers:
                name = c.name
                status = c.status
                image = c.image.tags[0] if c.image.tags else "<none>"
                config = "Privileged: On 🔥" if c.attrs['HostConfig']['Privileged'] else "Standard"
                print(f"  • {name:20} [{status:10}] {image:15} {config}")
        else:
            print("  No nihil containers found.")
        
        return 0


def main() -> int:
    """Main entry point"""
    try:
        controller = NihilController()
        return controller.run()
    except KeyboardInterrupt:
        print("\n\n[!] User interruption.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
