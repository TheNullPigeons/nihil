#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires pour nihilManager.py"""

import pytest
from unittest.mock import MagicMock, Mock, patch, call
import docker.errors

from nihil.nihilManager import NihilManager, ensure_filesystem
from nihil.nihilError import (
    DockerUnavailable,
    ImagePullFailed,
    ContainerCreateFailed,
    ContainerStartFailed,
    ContainerStopFailed,
    ContainerRemoveFailed,
)


class TestNihilManager:
    """Tests pour la classe NihilManager"""
    
    def test_init_success(self, mock_docker_client):
        """Test initialisation réussie avec Docker disponible"""
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                assert manager.client == mock_docker_client
                mock_docker_client.ping.assert_called_once()
    
    def test_init_docker_unavailable(self, mock_docker_client):
        """Test initialisation échoue si Docker indisponible"""
        mock_docker_client.ping.side_effect = docker.errors.DockerException("Connection refused")
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                with pytest.raises(DockerUnavailable):
                    NihilManager()
    
    def test_ensure_image_exists_image_found(self, mock_docker_client):
        """Test ensure_image_exists quand l'image existe déjà"""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                result = manager.ensure_image_exists("test-image:latest")
                
                assert result is True
                mock_docker_client.images.get.assert_called_once_with("test-image:latest")
    
    def test_ensure_image_exists_pull_success(self, mock_docker_client, mock_formatter):
        """Test ensure_image_exists quand il faut pull l'image"""
        # Image pas trouvée localement
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")
        # Pull réussit
        mock_docker_client.images.pull.return_value = MagicMock()
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                with patch('builtins.print'):  # Mock print pour éviter les sorties
                    manager = NihilManager()
                    result = manager.ensure_image_exists("test-image:latest")
                    
                    assert result is True
                    mock_docker_client.images.pull.assert_called_once_with("test-image:latest")
    
    def test_ensure_image_exists_pull_fails(self, mock_docker_client):
        """Test ensure_image_exists quand le pull échoue"""
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_docker_client.images.pull.side_effect = docker.errors.APIError("Pull failed", response=mock_response)
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                with patch('builtins.print'):
                    manager = NihilManager()
                    with pytest.raises(ImagePullFailed):
                        manager.ensure_image_exists("test-image:latest")
    
    def test_create_container_config_defaults(self, mock_docker_client):
        """Test création de container avec valeurs par défaut"""
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container
        mock_docker_client.images.get.return_value = MagicMock()  # Image exists
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                container = manager.create_container("test-container")
                
                # Vérifier que create a été appelé avec la bonne config
                call_args = mock_docker_client.containers.create.call_args
                assert call_args is not None
                config = call_args.kwargs
                
                assert config["name"] == "test-container"
                assert config["image"] == NihilManager.DEFAULT_IMAGE
                assert config["detach"] is True
                assert config["tty"] is True
                assert config["stdin_open"] is True
                assert config["privileged"] is False
                assert config["hostname"] == "test-container"
    
    def test_create_container_with_privileged(self, mock_docker_client):
        """Test création de container avec --privileged"""
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container
        mock_docker_client.images.get.return_value = MagicMock()
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                container = manager.create_container("test-container", privileged=True)
                
                call_args = mock_docker_client.containers.create.call_args
                assert call_args.kwargs["privileged"] is True
    
    def test_create_container_with_workspace(self, mock_docker_client):
        """Test création de container avec workspace volume"""
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container
        mock_docker_client.images.get.return_value = MagicMock()
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                container = manager.create_container("test-container", workspace="/tmp/test")
                
                call_args = mock_docker_client.containers.create.call_args
                volumes = call_args.kwargs.get("volumes", {})
                
                assert "/tmp/test" in volumes
                assert volumes["/tmp/test"]["bind"] == "/workspace"
                assert volumes["/tmp/test"]["mode"] == "rw"
    
    def test_create_container_with_network_mode(self, mock_docker_client):
        """Test création de container avec network_mode"""
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container
        mock_docker_client.images.get.return_value = MagicMock()
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                container = manager.create_container("test-container", network_mode="host")
                
                call_args = mock_docker_client.containers.create.call_args
                assert call_args.kwargs["network_mode"] == "host"
    
    def test_create_container_fails(self, mock_docker_client):
        """Test création de container échoue"""
        mock_docker_client.images.get.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_docker_client.containers.create.side_effect = docker.errors.APIError("Create failed", response=mock_response)
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                with pytest.raises(ContainerCreateFailed):
                    manager.create_container("test-container")
    
    def test_list_containers_filters_nihil(self, mock_docker_client):
        """Test list_containers filtre correctement les conteneurs nihil"""
        # Créer des mocks de conteneurs
        nihil_container = MagicMock()
        nihil_container.image.tags = ["ghcr.io/thenullpigeons/nihil-images:latest"]
        nihil_container.attrs = {"Config": {"Image": "nihil-images:latest"}}
        
        other_container = MagicMock()
        other_container.image.tags = ["ubuntu:latest"]
        other_container.attrs = {"Config": {"Image": "ubuntu:latest"}}
        
        mock_docker_client.containers.list.return_value = [nihil_container, other_container]
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                containers = manager.list_containers()
                
                # Doit retourner uniquement le conteneur nihil
                assert len(containers) == 1
                assert containers[0] == nihil_container
    
    def test_list_containers_filters_by_config_image(self, mock_docker_client):
        """Test list_containers filtre par Config.Image même sans tags"""
        nihil_container = MagicMock()
        nihil_container.image.tags = []  # Pas de tags (image supprimée)
        nihil_container.attrs = {"Config": {"Image": "nihil-images:latest"}}
        
        mock_docker_client.containers.list.return_value = [nihil_container]
        
        with patch('nihil.nihilManager.docker.from_env', return_value=mock_docker_client):
            with patch('nihil.nihilManager.ensure_filesystem'):
                manager = NihilManager()
                containers = manager.list_containers()
                
                assert len(containers) == 1
                assert containers[0] == nihil_container
