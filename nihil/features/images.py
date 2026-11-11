#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registre d’images Nihil (variantes, noms courts pour l’affichage)."""

# Single source of truth for the image variants. Everything that needs the
# variant list (argparse choices, registry builders, source validation,
# descriptions) must derive it from here instead of re-typing the tuple.
VARIANTS = ("full", "ad", "web", "defender", "mobile")

# One-line description per variant, shown in the image listings.
VARIANT_DESCRIPTIONS = {
    "full": "The whole flock, every tool, every module",
    "ad": "Nest in their Active Directory",
    "web": "Beak through their web apps",
    "defender": "Blue Team, DFIR and threat hunting",
    "mobile": "Carry it into their pocket. Android and iOS",
}

# Image par défaut
DEFAULT_IMAGE = "ghcr.io/thenullpigeons/full:latest"

# Variantes : nom court -> tag complet
AVAILABLE_IMAGES = {
    "full": "ghcr.io/thenullpigeons/full:latest",
    "ad": "ghcr.io/thenullpigeons/ad:latest",
    "web": "ghcr.io/thenullpigeons/web:latest",
    "defender": "ghcr.io/thenullpigeons/defender:latest",
    "mobile": "ghcr.io/thenullpigeons/mobile:latest",
}

# Tag complet -> nom d’affichage compact
SHORT_NAMES = {
    "ghcr.io/thenullpigeons/full:latest": "full:main",
    "ghcr.io/thenullpigeons/full:flock": "full",
    "ghcr.io/thenullpigeons/ad:latest": "ad:main",
    "ghcr.io/thenullpigeons/ad:nest": "ad",
    "ghcr.io/thenullpigeons/web:latest": "web:main",
    "ghcr.io/thenullpigeons/web:beak": "web",
    "ghcr.io/thenullpigeons/defender:latest": "defender:main",
    "ghcr.io/thenullpigeons/defender:coo": "defender",
    "ghcr.io/thenullpigeons/mobile:latest": "mobile:main",
    "ghcr.io/thenullpigeons/mobile:carrier": "mobile",
}


def short_image_name(full_tag: str) -> str:
    """Retourne un nom court pour l’affichage à partir du tag complet.

    Exemples:
        ‘ghcr.io/thenullpigeons/web:latest’ -> ‘web:main’
        ‘unknown/my-image:v1’ -> ‘my-image:v1’
    """
    if full_tag in SHORT_NAMES:
        return SHORT_NAMES[full_tag]
    if full_tag.startswith("nihil/"):
        rest = full_tag[len("nihil/"):]
        variant, _, tag = rest.partition(":")
        return f"{variant}:{tag}" if tag else variant
    name = full_tag.split("/")[-1] if "/" in full_tag else full_tag
    return name
