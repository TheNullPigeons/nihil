import argparse
import sys
from typing import Optional


class NihilController:
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="nihil",
            description="Nihil - by 0xbbuddha and Goultarde",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  nihil --version          Display version
  nihil --help             Display this help
            """
        )
        
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {self._get_version()}"
        )
        
        subparsers = parser.add_subparsers(
            dest="command",
            help="Available commands",
            metavar="COMMAND"
        )
        
        info_parser = subparsers.add_parser(
            "info",
            help="Display information about Nihil"
        )
        
        version_parser = subparsers.add_parser(
            "version",
            help="Display Nihil version"
        )
        
        return parser
    
    def _get_version(self) -> str:
        from nihil import __version__
        return __version__
    
    def run(self, args: Optional[list] = None) -> int:
        parsed_args = self.parser.parse_args(args)
        
        if parsed_args.command == "info":
            self._handle_info()
            return 0
        elif parsed_args.command == "version":
            print(f"Nihil version {self._get_version()}")
            return 0
        elif parsed_args.command is None:
            self.parser.print_help()
            return 0
        
        return 0
    
    def _handle_info(self) -> None:
        print("Nihil - by 0xbbuddha and Goultarde")
        print(f"Version: {self._get_version()}")
        print("\nThis project is under development.")


def main() -> int:
    try:
        controller = NihilController()
        return controller.run()
    except KeyboardInterrupt:
        print("\n\nUser interruption.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

