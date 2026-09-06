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
        assert "blueteam" in AVAILABLE_IMAGES

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

    def test_known_blueteam_returns_blueteam(self):
        assert short_image_name("ghcr.io/thenullpigeons/blueteam:latest") == "blueteam"

    def test_known_blueteam_coo_returns_blueteam(self):
        assert short_image_name("ghcr.io/thenullpigeons/blueteam:coo") == "blueteam"

    def test_unknown_with_slash_uses_last_part(self):
        assert short_image_name("registry/foo/bar:v1") == "bar:v1"

    def test_unknown_no_slash_unchanged(self):
        assert short_image_name("localonly") == "localonly"


def test_inventory_does_not_depend_on_active_source():
    from types import SimpleNamespace
    from unittest.mock import Mock
    import docker
    from nihil.manager import NihilManager
    from nihil.features.images import AVAILABLE_IMAGES

    def image(reference, image_id, labels=None):
        return SimpleNamespace(tags=[reference], id=image_id,
                               attrs={"Config": {"Labels": labels or {}}})

    upstream = image("ghcr.io/thenullpigeons/full:latest", "upstream")
    personal = image("ghcr.io/alice/full:nihil-full-custom", "personal")
    snapshot = image("nihil/full:nihil_full-custom", "old")
    unrelated = image("redis:latest", "redis")
    manager = NihilManager.__new__(NihilManager)
    manager.personal_image_repo = "alice/nihil-images"
    manager.client = Mock()
    manager.client.images.list.return_value = [upstream, personal, snapshot, unrelated]
    refs = {i.tags[0]: i for i in (upstream, personal, snapshot)}
    def lookup(reference):
        if reference not in refs:
            raise docker.errors.ImageNotFound(reference)
        return refs[reference]
    manager.client.images.get.side_effect = lookup
    current = SimpleNamespace(image=personal, attrs={"Config": {"Image": personal.tags[0]}})
    old = SimpleNamespace(image=snapshot, attrs={"Config": {"Image": personal.tags[0]}})
    missing = SimpleNamespace(image=snapshot, attrs={"Config": {"Image": "ghcr.io/alice/web:missing"}})
    pinned_id = SimpleNamespace(image=personal, attrs={"Config": {"Image": "sha256:personal"}})
    manager.client.containers.list.return_value = [current, old, missing]

    for registry in (AVAILABLE_IMAGES, {"full": personal.tags[0]}):
        manager.AVAILABLE_IMAGES = registry
        assert manager.list_images() == [upstream, personal, snapshot]
        assert manager.list_containers() == [current, old, missing]
        assert manager.get_image_source(upstream) == "upstream"
        assert manager.get_image_source(personal) == "personal"
        assert manager.get_image_source(snapshot) == "local"
        assert manager.get_container_source(old) == "personal"


def test_labeled_images_from_other_forks_are_included():
    from types import SimpleNamespace
    from nihil.manager import NihilManager

    manager = NihilManager.__new__(NihilManager)
    labels = {"org.nihil.app": "Nihil"}
    img = SimpleNamespace(tags=["ghcr.io/previous-owner/full:custom", "nihil/full:backup"],
                          attrs={"Config": {"Labels": labels}})
    assert manager.get_image_source(img) == "personal"
    img.tags = []
    assert manager.get_image_source(img) == "local"
    assert manager.image_source("ghcr.io/stranger/redis:latest") == "Unknown"
