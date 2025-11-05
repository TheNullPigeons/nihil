"""Contrôleur principal pour la CLI de Nihil"""
import argparse
import sys
from typing import Optional


class NihilController:
    """Contrôleur principal de Nihil"""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Crée le parser d'arguments pour la CLI"""
        parser = argparse.ArgumentParser(
            prog="nihil",
            description="Nihil - Une alternative minimaliste à Exegol",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Exemples:
  nihil --version          Affiche la version
  nihil --help             Affiche cette aide
            """
        )
        
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {self._get_version()}"
        )
        
        # Sous-commandes
        subparsers = parser.add_subparsers(
            dest="command",
            help="Commandes disponibles",
            metavar="COMMAND"
        )
        
        # Commande info
        info_parser = subparsers.add_parser(
            "info",
            help="Affiche des informations sur Nihil"
        )
        
        # Commande version (alternative)
        version_parser = subparsers.add_parser(
            "version",
            help="Affiche la version de Nihil"
        )
        
        return parser
    
    def _get_version(self) -> str:
        """Récupère la version depuis le module"""
        from nihil import __version__
        return __version__
    
    def run(self, args: Optional[list] = None) -> int:
        """Exécute le contrôleur avec les arguments fournis"""
        parsed_args = self.parser.parse_args(args)
        
        if parsed_args.command == "info":
            self._handle_info()
            return 0
        elif parsed_args.command == "version":
            print(f"Nihil version {self._get_version()}")
            return 0
        elif parsed_args.command is None:
            # Pas de commande spécifiée, afficher l'aide
            self.parser.print_help()
            return 0
        
        return 0
    
    def _handle_info(self) -> None:
        """Gère la commande info"""
        print("Nihil - Une alternative minimaliste à Exegol")
        print(f"Version: {self._get_version()}")
        print("\nCe projet est en cours de développement.")


def main() -> int:
    """Point d'entrée principal de Nihil"""
    try:
        controller = NihilController()
        return controller.run()
    except KeyboardInterrupt:
        print("\n\nInterruption par l'utilisateur.")
        return 130
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        return 1

