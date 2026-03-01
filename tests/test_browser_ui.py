#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour nihil.features.browser_ui (mots de passe, session, is_page_ready)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from nihil.features import browser_ui


@pytest.fixture
def temp_passwords_file(tmp_path, monkeypatch):
    """Fichier JSON temporaire pour les mots de passe Browser UI."""
    f = tmp_path / "browser_ui_passwords.json"
    monkeypatch.setattr(
        "nihil.features.browser_ui.BROWSER_UI_PASSWORDS_FILE",
        f,
    )
    return f


class TestBrowserUIPasswords:
    """save_password, load_password, clear_password."""

    def test_save_password_creates_file(self, temp_passwords_file):
        browser_ui.save_password("mycontainer", "secret123")
        assert temp_passwords_file.exists()
        assert "mycontainer" in temp_passwords_file.read_text()
        assert "secret123" in temp_passwords_file.read_text()

    def test_load_password_returns_saved(self, temp_passwords_file):
        browser_ui.save_password("c1", "pwd1")
        assert browser_ui.load_password("c1") == "pwd1"

    def test_load_password_returns_none_unknown_container(self, temp_passwords_file):
        assert browser_ui.load_password("unknown") is None

    def test_load_password_returns_none_missing_file(self, temp_passwords_file):
        assert not temp_passwords_file.exists()
        assert browser_ui.load_password("any") is None

    def test_clear_password_removes_entry(self, temp_passwords_file):
        browser_ui.save_password("c1", "p1")
        browser_ui.clear_password("c1")
        assert browser_ui.load_password("c1") is None

    def test_clear_password_empty_file_removes_file(self, temp_passwords_file):
        browser_ui.save_password("only", "p")
        browser_ui.clear_password("only")
        assert not temp_passwords_file.exists()


class TestGetSessionStrForRecap:
    """get_session_str_for_recap avec mock container."""

    def test_returns_root_password_when_stored(self, temp_passwords_file):
        browser_ui.save_password("demo", "mypass")
        container = MagicMock()
        container.attrs = {"Config": {"Env": []}}
        assert browser_ui.get_session_str_for_recap(container, "demo") == "root:mypass"

    def test_returns_root_star_when_env_has_password_but_not_stored(self, temp_passwords_file):
        container = MagicMock()
        container.attrs = {"Config": {"Env": ["NIHIL_BROWSER_UI_PASSWORD=hidden"]}}
        assert browser_ui.get_session_str_for_recap(container, "demo") == "root:***"

    def test_returns_none_when_no_password(self, temp_passwords_file):
        container = MagicMock()
        container.attrs = {"Config": {"Env": []}}
        assert browser_ui.get_session_str_for_recap(container, "other") is None


class TestIsPageReady:
    """is_page_ready (mock HTTP)."""

    def test_returns_true_on_200_with_nihil(self):
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = b"<title>Nihil</title>"
        with patch("nihil.features.browser_ui.urlopen") as m:
            m.return_value.__enter__.return_value = resp
            m.return_value.__exit__.return_value = None
            assert browser_ui.is_page_ready(6901) is True

    def test_returns_false_on_200_without_nihil(self):
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = b"<title>Other</title>"
        with patch("nihil.features.browser_ui.urlopen") as m:
            m.return_value.__enter__.return_value = resp
            m.return_value.__exit__.return_value = None
            assert browser_ui.is_page_ready(6901) is False

    def test_returns_false_on_404(self):
        resp = MagicMock()
        resp.status = 404
        with patch("nihil.features.browser_ui.urlopen") as m:
            m.return_value.__enter__.return_value = resp
            m.return_value.__exit__.return_value = None
            assert browser_ui.is_page_ready(6901) is False

    def test_returns_false_on_connection_error(self):
        from urllib.error import URLError
        with patch("nihil.features.browser_ui.urlopen") as m:
            m.side_effect = URLError("connection refused")
            assert browser_ui.is_page_ready(6999) is False
