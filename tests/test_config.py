#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour nihil.config (chemins et ensure_filesystem)."""

import pytest
from pathlib import Path

from nihil.config import (
    NIHIL_HOME,
    BROWSER_UI_PASSWORDS_FILE,
    MY_RESOURCES_DIR,
    ensure_filesystem,
)
class TestConfigPaths:
    """Vérification des constantes de chemins."""

    def test_nihil_home_sous_home(self):
        assert NIHIL_HOME == Path.home() / ".nihil"

    def test_browser_ui_passwords_file(self):
        assert BROWSER_UI_PASSWORDS_FILE == NIHIL_HOME / "browser_ui_passwords.json"

    def test_my_resources_dir(self):
        assert MY_RESOURCES_DIR == NIHIL_HOME / "my-resources"


class TestEnsureFilesystem:
    """Vérification de ensure_filesystem (avec répertoire temporaire)."""

    def test_ensure_filesystem_creates_setup_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nihil.config.defaults.NIHIL_HOME", tmp_path / "nihil")
        ensure_filesystem()
        base = tmp_path / "nihil" / "my-resources" / "setup"
        assert (base / "zsh").is_dir()
        assert (base / "zsh" / "zshrc").exists()
        assert (base / "zsh" / "aliases").exists()
        assert (base / "zsh" / "history").exists()
        assert (base / "nvim").is_dir()
        assert (base / "nvim" / "init.vim").exists()
        assert (base / "tmux").is_dir()
        assert (base / "tmux" / "tmux.conf").exists()

    def test_ensure_filesystem_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nihil.config.defaults.NIHIL_HOME", tmp_path / "nihil")
        ensure_filesystem()
        ensure_filesystem()
        base = tmp_path / "nihil" / "my-resources" / "setup"
        assert (base / "zsh" / "zshrc").exists()
