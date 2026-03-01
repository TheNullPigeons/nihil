#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests basiques pour le point d'entrée CLI (main, --version)."""

import pytest
from unittest.mock import patch


class TestMainEntryPoint:
    """Vérification que main() et le parser répondent correctement."""

    def test_main_returns_int(self):
        from nihil.cli.controller import main
        with patch("sys.argv", ["nihil", "version"]):
            exit_code = main()
        assert isinstance(exit_code, int)
        assert exit_code == 0

    def test_main_with_version_exits_zero(self):
        """--version (via 'version' subcommand) retourne 0."""
        from nihil.cli.controller import main
        with patch("sys.argv", ["nihil", "version"]):
            assert main() == 0
