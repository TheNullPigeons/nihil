#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests basiques pour le point d'entrée CLI (main, --version)."""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


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


class TestUninstallForce:
    """Tests pour `nihil uninstall <image> --force`."""

    def _make_controller(self, manager, formatter):
        from nihil.cli.controller import NihilController
        controller = NihilController.__new__(NihilController)
        controller.manager = manager
        controller.formatter = formatter
        return controller

    def test_force_removes_running_container_then_image(self, mock_formatter):
        """--force arrête/supprime le conteneur qui utilise l'image, sans prompt,
        et un conteneur parasite à image dangling ne casse pas la détection."""
        image_ref = "ghcr.io/thenullpigeons/ad:latest"

        manager = MagicMock()
        manager.AVAILABLE_IMAGES = {"ad": image_ref}
        manager.client.images.get.return_value = MagicMock(id="sha256:ADID")

        # Conteneur parasite placé EN PREMIER : son image est dangling, donc tout
        # accès à ses metadata lève. L'ancien code avortait alors toute la détection.
        parasite = MagicMock(name="parasite")
        parasite.attrs.get.side_effect = Exception("dangling image metadata")

        ad_container = MagicMock()
        ad_container.name = "pentest"
        ad_container.status = "running"
        ad_container.attrs = {"Image": "sha256:ADID", "Config": {"Image": image_ref}}

        manager.client.containers.list.return_value = [parasite, ad_container]
        manager.get_container.return_value = ad_container

        controller = self._make_controller(manager, mock_formatter)
        args = SimpleNamespace(names=["ad"], force=True)

        with patch("builtins.input") as mock_input:
            rc = controller._cmd_uninstall(args)

        assert rc == 0
        # Aucun prompt interactif avec --force.
        mock_input.assert_not_called()
        # Le conteneur en cours est arrêté puis supprimé.
        manager.stop_container.assert_called_once_with(ad_container)
        manager.remove_container.assert_called_once_with(ad_container, force=True)
        # L'image est ensuite supprimée avec force=True.
        manager.remove_image.assert_called_once_with(image_ref, force=True)
