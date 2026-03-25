#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour nihil.features.images (registre et short_image_name)."""

import pytest

from nihil.features.images import (
    DEFAULT_IMAGE,
    AVAILABLE_IMAGES,
    short_image_name,
)


class TestImagesRegistry:
    """Constantes du registre d'images."""

    def test_default_image(self):
        assert DEFAULT_IMAGE == "ghcr.io/thenullpigeons/full:latest"

    def test_available_images_has_full_ad_web_ctf(self):
        assert "full" in AVAILABLE_IMAGES
        assert "ad" in AVAILABLE_IMAGES
        assert "web" in AVAILABLE_IMAGES
        assert "ctf" in AVAILABLE_IMAGES

    def test_full_and_default_match(self):
        assert AVAILABLE_IMAGES["full"] == DEFAULT_IMAGE


class TestShortImageName:
    """Nom court pour l'affichage."""

    def test_known_full_returns_full(self):
        assert short_image_name("ghcr.io/thenullpigeons/full:latest") == "full"

    def test_known_full_flock_returns_full(self):
        assert short_image_name("ghcr.io/thenullpigeons/full:flock") == "full"

    def test_known_ad_returns_ad(self):
        assert short_image_name("ghcr.io/thenullpigeons/ad:latest") == "ad"

    def test_known_ad_nest_returns_ad(self):
        assert short_image_name("ghcr.io/thenullpigeons/ad:nest") == "ad"

    def test_known_web_returns_web(self):
        assert short_image_name("ghcr.io/thenullpigeons/web:latest") == "web"

    def test_known_web_beak_returns_web(self):
        assert short_image_name("ghcr.io/thenullpigeons/web:beak") == "web"

    def test_known_ctf_returns_ctf(self):
        assert short_image_name("ghcr.io/thenullpigeons/ctf:latest") == "ctf"

    def test_known_ctf_flag_returns_ctf(self):
        assert short_image_name("ghcr.io/thenullpigeons/ctf:flag") == "ctf"

    def test_unknown_with_slash_uses_last_part(self):
        assert short_image_name("registry/foo/bar:v1") == "bar:v1"

    def test_unknown_no_slash_unchanged(self):
        assert short_image_name("localonly") == "localonly"
