#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration et chemins Nihil (fichiers utilisateur, répertoires)."""

from pathlib import Path

# Répertoire de base utilisateur Nihil
NIHIL_HOME = Path.home() / ".nihil"

# Fichier de stockage des mots de passe Browser UI (générés par le wrapper)
BROWSER_UI_PASSWORDS_FILE = NIHIL_HOME / "browser_ui_passwords.json"

# Répertoire my-resources monté dans les containers
MY_RESOURCES_DIR = NIHIL_HOME / "my-resources"


def ensure_filesystem() -> None:
    """Crée les répertoires et fichiers par défaut (~/.nihil/my-resources/setup/...)."""
    base = NIHIL_HOME / "my-resources" / "setup"

    # --- zsh ---
    zsh_path = base / "zsh"
    zsh_path.mkdir(parents=True, exist_ok=True)
    zshrc_path = zsh_path / "zshrc"
    if not zshrc_path.exists():
        zshrc_path.write_text(
            "# Ajoutez ici votre configuration zsh personnalisée\n"
            "# Elle sera chargée automatiquement dans vos containers Nihil\n"
        )
    aliases_path = zsh_path / "aliases"
    if not aliases_path.exists():
        aliases_path.write_text(
            "# Ajoutez ici vos alias personnalisés\n"
            "# Exemple : alias ll='ls -lah'\n"
        )
    history_path = zsh_path / "history"
    if not history_path.exists():
        history_path.write_text(
            "# Ajoutez ici vos commandes à pré-charger dans l'historique zsh\n"
        )

    # --- nvim ---
    nvim_path = base / "nvim"
    nvim_path.mkdir(parents=True, exist_ok=True)
    init_vim = nvim_path / "init.vim"
    if not init_vim.exists():
        init_vim.write_text(
            "\" Ajoutez ici votre configuration Neovim personnalisée\n"
            "\" Elle sera copiée dans ~/.config/nvim/ à l'intérieur du container\n"
        )

    # --- tmux ---
    tmux_path = base / "tmux"
    tmux_path.mkdir(parents=True, exist_ok=True)
    tmux_conf = tmux_path / "tmux.conf"
    if not tmux_conf.exists():
        tmux_conf.write_text(
            "# Ajoutez ici votre configuration tmux personnalisée\n"
            "# Elle sera fusionnée dans ~/.tmux.conf à l'intérieur du container\n"
            "# Exemple :\n"
            "# set -g mouse on\n"
        )

    # --- user setup script ---
    user_setup = base / "load_user_setup.sh"
    if not user_setup.exists():
        user_setup.write_text(
            "#!/bin/bash\n"
            "# Runs once at first container start.\n"
            "# Place your custom installs here.\n"
        )
        user_setup.chmod(0o755)
