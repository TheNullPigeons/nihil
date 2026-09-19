#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires pour nihilHistory.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from nihil.utils import log_command, HISTORY_PATH


class TestNihilHistory:
    """Tests pour le module nihilHistory"""
    
    def test_log_command_writes_to_file(self, temp_history_path):
        """Test log_command écrit dans le fichier"""
        log_command(["start", "my-container"], exit_code=0)
        
        assert temp_history_path.exists()
        content = temp_history_path.read_text()
        
        assert "nihil start my-container" in content
        assert content.endswith("\n")
    
    def test_log_command_creates_directory(self, tmp_path, monkeypatch):
        """Test log_command crée le répertoire si nécessaire"""
        history_file = tmp_path / "new_dir" / "history.log"
        monkeypatch.setattr("nihil.utils.history.HISTORY_PATH", history_file)
        
        log_command(["test"], exit_code=0)
        
        assert history_file.parent.exists()
        assert history_file.exists()
    
    def test_log_command_handles_errors_silently(self, tmp_path, monkeypatch):
        """Test log_command gère les erreurs silencieusement"""
        history_file = tmp_path / "history.log"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text("existing")
        history_file.chmod(0o000)  # Pas d'accès
        
        monkeypatch.setattr("nihil.utils.history.HISTORY_PATH", history_file)
        
        try:
            log_command(["test"], exit_code=0)
        except Exception:
            pytest.fail("log_command should handle errors silently")
        
        history_file.chmod(0o644)
    
    def test_log_command_format(self, temp_history_path):
        """Test le format de la ligne écrite"""
        log_command(["start", "test-container", "--privileged"], exit_code=0)
        
        content = temp_history_path.read_text()
        lines = content.strip().split("\n")
        
        assert len(lines) == 1
        assert lines[0] == "nihil start test-container --privileged"
    
    def test_log_command_multiple_entries(self, temp_history_path):
        """Test plusieurs entrées dans le fichier"""
        log_command(["start", "container1"], exit_code=0)
        log_command(["stop", "container2"], exit_code=0)
        log_command(["remove", "container3"], exit_code=0)

        content = temp_history_path.read_text()
        lines = [l for l in content.strip().split("\n") if l]

        assert len(lines) == 3
        assert "nihil start container1" in lines[0]
        assert "nihil stop container2" in lines[1]
        assert "nihil remove container3" in lines[2]

    def test_log_command_redacts_env_value(self, temp_history_path):
        """--env can carry a secret: its value must never be logged."""
        log_command(["start", "c1", "--env", "API_TOKEN=eyJhbGciOi", "--env", "FOO=bar"], exit_code=0)

        content = temp_history_path.read_text()
        assert "eyJhbGciOi" not in content
        assert "FOO=bar" not in content
        assert content.strip() == "nihil start c1 --env *** --env ***"

    def test_log_command_redacts_env_equals_form(self, temp_history_path):
        """--env=KEY=VALUE form (argparse) is also masked."""
        log_command(["start", "c1", "--env=API_TOKEN=secret"], exit_code=0)

        content = temp_history_path.read_text()
        assert "secret" not in content
        assert content.strip() == "nihil start c1 --env=***"

    def test_log_command_redacts_workspace_and_vpn_paths(self, temp_history_path):
        """--workspace/--vpn can leak the client name through a file path."""
        log_command(
            ["start", "acme-corp", "--workspace", "/home/user/engagements/acme-corp", "--vpn", "/home/user/vpn/acme.ovpn"],
            exit_code=0,
        )

        content = temp_history_path.read_text()
        assert "acme-corp" not in content.replace("nihil start acme-corp", "", 1)
        assert content.strip() == "nihil start acme-corp --workspace *** --vpn ***"

    def test_log_command_keeps_bare_vpn_flag(self, temp_history_path):
        """--vpn with no value (nargs='?') must not swallow the next flag."""
        log_command(["start", "c1", "--vpn", "--privileged"], exit_code=0)

        content = temp_history_path.read_text()
        assert content.strip() == "nihil start c1 --vpn --privileged"
