import argparse
import sys
from typing import Optional
from nihil.docker_manager import DockerManager
from nihil import __version__


class NihilController:
    
    def __init__(self):
        self.parser = self._create_parser()
        self.manager = None
    
    def _create_parser(self) -> argparse.ArgumentParser:
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
    
    def run(self, args: Optional[list] = None) -> int:
        parsed_args = self.parser.parse_args(args)
        
        if parsed_args.command is None:
            self.parser.print_help()
            return 0
        
        if parsed_args.command == "version":
            print(f"Nihil version {__version__}")
            return 0
        
        # Initialize Docker manager for commands that need it
        try:
            self.manager = DockerManager()
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
        
        print(f"[*] Looking for container '{container_name}'...")
        container = self.manager.get_container(container_name)
        
        if container:
            print(f"[*] Container '{container_name}' found.")
            if container.status == "running":
                print(f"[!] Container '{container_name}' is already running.")
            else:
                print(f"[*] Starting container '{container_name}'...")
                if self.manager.start_container(container):
                    print(f"[✓] Container '{container_name}' started successfully.")
                else:
                    return 1
        else:
            print(f"[*] Container '{container_name}' doesn't exist. Creating...")
            container = self.manager.create_container(
                name=container_name,
                privileged=args.privileged,
                network_mode=args.network if args.network else None,
                workspace=args.workspace
            )
            print(f"[*] Container '{container_name}' created.")
            print(f"[*] Starting container '{container_name}'...")
            if self.manager.start_container(container):
                print(f"[✓] Container '{container_name}' created and started successfully.")
            else:
                return 1
        
        # Connect to container if requested
        if not args.no_shell:
            print(f"[*] Connecting to container '{container_name}'...")
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
    try:
        controller = NihilController()
        return controller.run()
    except KeyboardInterrupt:
        print("\n\n[!] User interruption.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
