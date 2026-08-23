#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires pour platform_info.py"""

from unittest.mock import patch

from nihil.utils.platform_info import get_image_platform


def test_get_image_platform_native_amd64():
    """Ne force pas la plateforme sur un hôte amd64 natif."""
    with patch("nihil.utils.platform_info.platform.machine", return_value="x86_64"):
        assert get_image_platform() is None


def test_get_image_platform_arm64():
    """Force linux/amd64 sur un hôte ARM64 pour les images Nihil."""
    with patch("nihil.utils.platform_info.platform.machine", return_value="arm64"):
        assert get_image_platform() == "linux/amd64"


def test_get_image_platform_unknown_architecture():
    """Laisse Docker choisir sur une architecture non prise en charge."""
    with patch("nihil.utils.platform_info.platform.machine", return_value="riscv64"):
        assert get_image_platform() is None
