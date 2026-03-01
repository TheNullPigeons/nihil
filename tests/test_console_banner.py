#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour nihil.console.banner."""

import pytest
from io import StringIO

from nihil.console.banner import get_banner, get_compact_banner, print_banner, print_compact_banner


class TestGetBanner:
    def test_returns_non_empty_string(self):
        assert get_banner()
        assert len(get_banner().strip()) > 0

    def test_contains_nihil_or_ascii_art(self):
        b = get_banner()
        assert "NIHIL" in b or "Nihil" in b or "█" in b


class TestGetCompactBanner:
    def test_returns_non_empty_string(self):
        assert get_compact_banner().strip()

    def test_contains_nihil(self):
        assert "NIHIL" in get_compact_banner()


class TestPrintBanner:
    def test_print_banner_writes_to_buffer(self):
        buf = StringIO()
        print_banner(file=buf)
        assert buf.getvalue()
        assert "NIHIL" in buf.getvalue() or "█" in buf.getvalue()

    def test_print_compact_banner_writes_to_buffer(self):
        buf = StringIO()
        print_compact_banner(file=buf)
        # print_compact_banner utilise get_banner() (full ASCII art)
        assert "TheNullPigeons" in buf.getvalue()
