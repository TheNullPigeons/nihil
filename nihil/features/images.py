#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registre d’images Nihil (variantes, noms courts pour l’affichage)."""

# Image par défaut
DEFAULT_IMAGE = "ghcr.io/thenullpigeons/full:latest"

# Variantes : nom court -> tag complet
AVAILABLE_IMAGES = {
    "full": "ghcr.io/thenullpigeons/full:latest",
    "ad": "ghcr.io/thenullpigeons/ad:latest",
    "web": "ghcr.io/thenullpigeons/web:latest",
    "ctf": "ghcr.io/thenullpigeons/ctf:latest",
}

# Tag complet -> nom d’affichage compact
SHORT_NAMES = {
    "ghcr.io/thenullpigeons/full:latest": "full",
    "ghcr.io/thenullpigeons/full:flock": "full",
    "ghcr.io/thenullpigeons/ad:latest": "ad",
    "ghcr.io/thenullpigeons/ad:nest": "ad",
    "ghcr.io/thenullpigeons/web:latest": "web",
    "ghcr.io/thenullpigeons/web:beak": "web",
    "ghcr.io/thenullpigeons/ctf:latest": "ctf",
    "ghcr.io/thenullpigeons/ctf:flag": "ctf",
}


def short_image_name(full_tag: str) -> str:
    """Retourne un nom court pour l’affichage à partir du tag complet.

    Exemples:
        ‘ghcr.io/thenullpigeons/web:latest’ -> ‘web’
        ‘unknown/my-image:v1’ -> ‘my-image:v1’
    """
    if full_tag in SHORT_NAMES:
        return SHORT_NAMES[full_tag]
    if full_tag.startswith("nihil/"):
        rest = full_tag[len("nihil/"):]
        variant, _, tag = rest.partition(":")
        return f"{variant} [{tag}]" if tag else variant
    name = full_tag.split("/")[-1] if "/" in full_tag else full_tag
    return name
