#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour nihil.cli.parser (create_parser, sous-commandes, arguments)."""

import pytest

from nihil.cli.parser import create_parser


class TestCreateParser:
    """Parser CLI créé correctement."""

    def test_parser_prog(self):
        parser = create_parser()
        assert parser.prog == "nihil"

    def test_version_action(self):
        parser = create_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--version"])
        assert exc.value.code == 0

    def test_subparsers_required_commands(self):
        parser = create_parser()
        # Sans argument de sous-commande, command est None
        args = parser.parse_args([])
        assert args.command is None

    def test_parse_info(self):
        parser = create_parser()
        args = parser.parse_args(["info"])
        assert args.command == "info"

    def test_parse_info_with_container(self):
        parser = create_parser()
        args = parser.parse_args(["info", "--container", "demo"])
        assert args.command == "info"
        assert args.container == "demo"

    def test_parse_start_minimal(self):
        parser = create_parser()
        args = parser.parse_args(["start", "myname"])
        assert args.command == "start"
        assert args.name == "myname"
        assert args.privileged is False
        assert args.network is None  # None = use config default (fallback: host)

    def test_parse_start_with_options(self):
        parser = create_parser()
        args = parser.parse_args([
            "start", "box", "--privileged", "--network", "docker",
            "--image", "web", "--browser-ui", "--no-shell",
        ])
        assert args.command == "start"
        assert args.name == "box"
        assert args.privileged is True
        assert args.network == "docker"
        assert args.image == "web"
        assert args.browser_ui is True
        assert args.no_shell is True

    def test_parse_stop(self):
        parser = create_parser()
        args = parser.parse_args(["stop", "c1"])
        assert args.command == "stop"
        assert args.name == "c1"

    def test_parse_remove(self):
        parser = create_parser()
        args = parser.parse_args(["remove", "a", "b", "--force"])
        assert args.command == "remove"
        assert args.names == ["a", "b"]
        assert args.force is True

    def test_parse_exec(self):
        parser = create_parser()
        args = parser.parse_args(["exec", "c1", "bash"])
        assert args.name == "c1"
        # command (nargs="*") contient la commande à exécuter
        assert args.command == ["bash"]

    def test_parse_install(self):
        parser = create_parser()
        args = parser.parse_args(["install", "full"])
        assert args.command == "install"
        assert args.image == "full"

    def test_parse_doctor(self):
        parser = create_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"

    def test_parse_images(self):
        parser = create_parser()
        args = parser.parse_args(["images"])
        assert args.command == "images"

    def test_parse_completion(self):
        parser = create_parser()
        args = parser.parse_args(["completion", "zsh"])
        assert args.command == "completion"
        assert args.shell == "zsh"
