#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pytest configuration and shared fixtures"""

import pytest
from unittest.mock import MagicMock, Mock
from pathlib import Path


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing"""
    client = MagicMock()
    # Mock ping() to simulate successful connection
    client.ping.return_value = True
    
    # Mock images API
    client.images = MagicMock()
    
    # Mock containers API
    client.containers = MagicMock()
    
    return client


@pytest.fixture
def mock_formatter():
    """Mock formatter for testing"""
    from unittest.mock import MagicMock
    formatter = MagicMock()
    formatter.info.return_value = "[*] info"
    formatter.success.return_value = "[✓] success"
    formatter.error.return_value = "[✗] error"
    formatter.warning.return_value = "[!] warning"
    return formatter


@pytest.fixture
def temp_history_path(tmp_path, monkeypatch):
    """Temporary history file path for testing"""
    history_file = tmp_path / "history.log"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Monkeypatch the HISTORY_PATH in nihilHistory module
    from nihil.nihilHistory import HISTORY_PATH
    monkeypatch.setattr("nihil.nihilHistory.HISTORY_PATH", history_file)
    
    return history_file
