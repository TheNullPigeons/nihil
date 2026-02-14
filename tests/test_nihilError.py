#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires pour nihilError.py"""

import pytest
import sys

from nihil.nihilError import (
    NihilError,
    DockerUnavailable,
    ImagePullFailed,
    ContainerNotFound,
    ContainerCreateFailed,
    ImageRemoveFailed,
)


class TestNihilError:
    """Tests pour les exceptions Nihil"""
    
    def test_nihil_error_basic(self):
        """Test exception de base sans hint"""
        error = NihilError(message="Test error", exit_code=42)
        
        assert error.message == "Test error"
        assert error.exit_code == 42
        assert error.hint is None
        assert str(error) == "Test error"
    
    def test_nihil_error_with_hint(self):
        """Test exception avec hint"""
        error = NihilError(message="Test error", exit_code=42, hint="Try this")
        
        assert error.hint == "Try this"
        assert str(error) == "Test error\nHint: Try this"
    
    def test_docker_unavailable_exit_code(self):
        """Test DockerUnavailable a le bon exit code"""
        error = DockerUnavailable("Docker not running")
        
        assert error.exit_code == 2
        assert "Docker" in error.message
        assert error.hint is not None  # Hint par défaut
    
    def test_docker_unavailable_custom_hint(self):
        """Test DockerUnavailable avec hint personnalisé"""
        error = DockerUnavailable("Docker not running", hint="Custom hint")
        
        assert error.hint == "Custom hint"
    
    def test_image_pull_failed_exit_code(self):
        """Test ImagePullFailed a le bon exit code"""
        error = ImagePullFailed(image="test-image", message="Pull failed")
        
        assert error.exit_code == 3
        assert error.image == "test-image"
        assert "Pull failed" in error.message
    
    def test_container_not_found_exit_code(self):
        """Test ContainerNotFound a le bon exit code"""
        error = ContainerNotFound(name="my-container")
        
        assert error.exit_code == 4
        assert error.name == "my-container"
        assert "my-container" in error.message
    
    def test_container_create_failed_exit_code(self):
        """Test ContainerCreateFailed a le bon exit code"""
        error = ContainerCreateFailed(name="my-container", message="Create failed")
        
        assert error.exit_code == 6
        assert error.name == "my-container"
    
    def test_image_remove_failed_exit_code(self):
        """Test ImageRemoveFailed a le bon exit code"""
        error = ImageRemoveFailed(image="test-image", message="Remove failed")
        
        assert error.exit_code == 10
        assert error.image == "test-image"
