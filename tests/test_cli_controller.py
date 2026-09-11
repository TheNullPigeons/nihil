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


class TestStartShellCommand:
    """Tests pour le shell interactif lance par `nihil start`."""

    @staticmethod
    def _make_controller(default_shell):
        from nihil.cli.controller import NihilController
        controller = NihilController.__new__(NihilController)
        controller.config = SimpleNamespace(default_shell=default_shell)
        return controller

    def test_tmux_flag_overrides_default_shell(self):
        controller = self._make_controller("zsh")
        args = SimpleNamespace(tmux=True)
        assert controller._start_shell_command(args) == "tmux new-session -A -s nihil"

    def test_tmux_config_opens_tmux(self):
        controller = self._make_controller("tmux")
        args = SimpleNamespace(tmux=False)
        assert controller._start_shell_command(args) == "tmux new-session -A -s nihil"

    def test_bash_config_opens_bash(self):
        controller = self._make_controller("bash")
        args = SimpleNamespace(tmux=False)
        assert controller._start_shell_command(args) == "bash"

    def test_unknown_config_falls_back_to_zsh(self):
        controller = self._make_controller("fish")
        args = SimpleNamespace(tmux=False)
        assert controller._start_shell_command(args) == "zsh"


class TestVpnConfigResolution:
    """Tests pour `nihil start --vpn` sans chemin explicite."""

    @staticmethod
    def _make_controller():
        from nihil.cli.controller import NihilController
        return NihilController.__new__(NihilController)

    def test_vpn_file_is_returned_as_explicit_path(self, tmp_path):
        controller = self._make_controller()
        vpn_file = tmp_path / "lab.ovpn"
        vpn_file.write_text("client\n", encoding="utf-8")

        assert controller._resolve_vpn_config_path(str(vpn_file)) == str(vpn_file.resolve())

    def test_vpn_without_file_uses_default_client_ovpn(self, tmp_path, monkeypatch):
        import nihil.cli.controller as controller_module

        monkeypatch.setattr(controller_module, "NIHIL_HOME", tmp_path)
        vpn_dir = tmp_path / "vpn"
        vpn_dir.mkdir()
        vpn_file = vpn_dir / "client.ovpn"
        vpn_file.write_text("client\n", encoding="utf-8")

        controller = self._make_controller()

        assert controller._resolve_vpn_config_path(True) == str(vpn_file.resolve())

    def test_vpn_without_file_uses_only_ovpn(self, tmp_path, monkeypatch):
        import nihil.cli.controller as controller_module

        monkeypatch.setattr(controller_module, "NIHIL_HOME", tmp_path)
        vpn_dir = tmp_path / "vpn"
        vpn_dir.mkdir()
        vpn_file = vpn_dir / "htb.ovpn"
        vpn_file.write_text("client\n", encoding="utf-8")

        controller = self._make_controller()

        assert controller._resolve_vpn_config_path(True) == str(vpn_file.resolve())


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


class TestBuildPlatform:
    """Tests pour la plateforme passée à `docker build`."""

    @staticmethod
    def _make_controller(source):
        from nihil.cli.controller import NihilController

        controller = NihilController.__new__(NihilController)
        controller.config = SimpleNamespace(images_path=str(source))
        controller.formatter = MagicMock()
        controller.formatter.info.side_effect = lambda message: message
        controller.formatter.success.side_effect = lambda message: message
        controller.formatter.error.side_effect = lambda message: message
        return controller

    @staticmethod
    def _run_build(controller, variant, tag=None):
        args = SimpleNamespace(
            variant=variant,
            source=None,
            tag=tag,
            no_cache=False,
            log=None,
        )
        process = MagicMock()
        process.stdout.read1.return_value = b""
        process.returncode = 0

        with patch("subprocess.Popen", return_value=process) as popen:
            assert controller._cmd_build(args) == 0

        return popen.call_args.args[0]

    @pytest.mark.parametrize(
        ("variant", "dockerfile"),
        [
            ("full", "Dockerfile"),
            ("blueteam", "Dockerfile.blueteam"),
            ("test", "Dockerfile.test"),
        ],
    )
    def test_arm64_build_sets_amd64_platform(self, tmp_path, variant, dockerfile):
        """Les variantes principales ciblent linux/amd64 sur ARM64."""
        (tmp_path / dockerfile).touch()
        controller = self._make_controller(tmp_path)

        with patch("nihil.utils.get_image_platform", return_value="linux/amd64"):
            command = self._run_build(controller, variant)

        assert command[:2] == ["docker", "build"]
        assert command[command.index("--file") + 1] == str(tmp_path / dockerfile)
        assert command[command.index("--tag") + 1] == f"nihil/{variant}:local"
        assert command[command.index("--platform") + 1] == "linux/amd64"
        assert command[-1] == str(tmp_path)

    def test_amd64_build_keeps_custom_tag_without_platform(self, tmp_path):
        """Un build amd64 conserve le tag demandé sans forcer de plateforme."""
        (tmp_path / "Dockerfile").touch()
        controller = self._make_controller(tmp_path)

        with patch("nihil.utils.get_image_platform", return_value=None):
            command = self._run_build(controller, "full", tag="example/nihil:dev")

        assert "--platform" not in command
        assert command[command.index("--tag") + 1] == "example/nihil:dev"
        assert command[-1] == str(tmp_path)


class TestUninstallUnused:
    def make_controller(self, mock_formatter):
        from nihil.cli.controller import NihilController
        c = NihilController.__new__(NihilController)
        c.formatter = mock_formatter
        c.manager = MagicMock()
        c.manager.list_images.return_value = [
            SimpleNamespace(id="sha256:used", short_id="used", tags=[], attrs={"Size": 1}),
            SimpleNamespace(id="sha256:unused", short_id="unused", tags=[], attrs={"Size": 1}),
        ]
        return c

    def test_only_unused_removed_without_force_or_pruning(self, mock_formatter):
        c = self.make_controller(mock_formatter)
        c.manager.get_image_usage.return_value = {"sha256:used": ["stopped-lab"]}
        assert c._cmd_uninstall(SimpleNamespace(names=[], unused=True, force=True)) == 0
        c.manager.remove_unused_image.assert_called_once_with("sha256:unused")
        c.manager.remove_container.assert_not_called()
        c.manager.stop_container.assert_not_called()

    @pytest.mark.parametrize("usage", [None, {"sha256:used": ["lab"], "sha256:unused": ["new-lab"]}])
    def test_usage_rechecked_before_removal(self, mock_formatter, usage):
        c = self.make_controller(mock_formatter)
        c.manager.get_image_usage.side_effect = [{"sha256:used": ["lab"]}, usage]
        c._cmd_uninstall(SimpleNamespace(names=[], unused=True, force=True))
        c.manager.remove_unused_image.assert_not_called()

    def test_unknown_usage_aborts(self, mock_formatter):
        c = self.make_controller(mock_formatter)
        c.manager.get_image_usage.return_value = None
        assert c._cmd_uninstall(SimpleNamespace(names=[], unused=True, force=True)) == 1
        c.manager.remove_unused_image.assert_not_called()

    def test_declined_confirmation_removes_nothing(self, mock_formatter):
        c = self.make_controller(mock_formatter)
        c.manager.get_image_usage.return_value = {}
        with patch("builtins.input", return_value="n"):
            assert c._cmd_uninstall(SimpleNamespace(names=[], unused=True, force=False)) == 0
        c.manager.remove_unused_image.assert_not_called()

    def test_names_rejected(self, mock_formatter):
        c = self.make_controller(mock_formatter)
        assert c._cmd_uninstall(SimpleNamespace(names=["full"], unused=True, force=True)) == 1
        c.manager.remove_unused_image.assert_not_called()

    def test_parser(self):
        from nihil.cli.parser import create_parser
        args = create_parser().parse_args(["uninstall", "--unused"])
        assert args.unused is True
        assert args.names == []
