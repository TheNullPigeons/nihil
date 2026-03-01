#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registre d’images Nihil (variantes, noms courts pour l’affichage)."""

# Image par défaut
DEFAULT_IMAGE = "ghcr.io/thenullpigeons/nihil-images:latest"

# Variantes : nom court -> tag complet
AVAILABLE_IMAGES = {
    "base": "ghcr.io/thenullpigeons/nihil-images:latest",
    "ad": "ghcr.io/thenullpigeons/nihil-images-ad:latest",
    "active-directory": "ghcr.io/thenullpigeons/nihil-images-ad:latest",
    "web": "ghcr.io/thenullpigeons/nihil-images-web:latest",
}

# Tag complet -> nom d’affichage compact
SHORT_NAMES = {
    "ghcr.io/thenullpigeons/nihil-images:latest": "nihil",
    "ghcr.io/thenullpigeons/nihil-images-ad:latest": "nihil-ad",
    "ghcr.io/thenullpigeons/nihil-images-web:latest": "nihil-web",
}


def short_image_name(full_tag: str) -> str:
    """Retourne un nom court pour l’affichage à partir du tag complet.

    Exemples:
        'ghcr.io/thenullpigeons/nihil-images-web:latest' -> 'nihil-web'
        'unknown/my-image:v1' -> 'my-image:v1'
    """
    if full_tag in SHORT_NAMES:
        return SHORT_NAMES[full_tag]
    name = full_tag.split("/")[-1] if "/" in full_tag else full_tag
    return name.replace("nihil-images", "nihil", 1)
