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
        assert DEFAULT_IMAGE == "ghcr.io/thenullpigeons/nihil-images:latest"

    def test_available_images_has_base_ad_web(self):
        assert "base" in AVAILABLE_IMAGES
        assert "ad" in AVAILABLE_IMAGES
        assert "web" in AVAILABLE_IMAGES
        assert "active-directory" in AVAILABLE_IMAGES

    def test_base_and_default_match(self):
        assert AVAILABLE_IMAGES["base"] == DEFAULT_IMAGE

    def test_ad_and_active_directory_same_tag(self):
        assert AVAILABLE_IMAGES["ad"] == AVAILABLE_IMAGES["active-directory"]


class TestShortImageName:
    """Nom court pour l'affichage."""

    def test_known_base_returns_nihil(self):
        assert short_image_name("ghcr.io/thenullpigeons/nihil-images:latest") == "nihil"

    def test_known_ad_returns_nihil_ad(self):
        assert short_image_name("ghcr.io/thenullpigeons/nihil-images-ad:latest") == "nihil-ad"

    def test_known_web_returns_nihil_web(self):
        assert short_image_name("ghcr.io/thenullpigeons/nihil-images-web:latest") == "nihil-web"

    def test_unknown_with_slash_uses_last_part(self):
        assert short_image_name("registry/foo/bar:v1") == "bar:v1"

    def test_unknown_no_slash_unchanged(self):
        assert short_image_name("localonly") == "localonly"

    def test_nihil_images_replaced_by_nihil(self):
        # Quand le tag n'est pas dans SHORT_NAMES mais contient nihil-images
        result = short_image_name("ghcr.io/org/nihil-images-custom:latest")
        assert "nihil" in result
        assert "nihil-images" not in result
