# Tests unitaires pour Nihil

Ce dossier contient les tests unitaires pour le projet Nihil, utilisant `pytest` et `unittest.mock`.

## Structure

- `conftest.py` : Fixtures partagées (mock Docker client, formatter, etc.)
- `test_nihilManager.py` : Tests pour la logique métier Docker (filtrage, création de containers, etc.)
- `test_nihilError.py` : Tests pour les exceptions et codes de sortie
- `test_nihilFormatter.py` : Tests pour le formatage (ANSI, couleurs)
- `test_nihilHistory.py` : Tests pour l'historique des commandes

## Installation

```bash
pip install -r requirements-dev.txt
```

## Exécution

Depuis le répertoire `nihil/` :

```bash
# Tous les tests
pytest

# Un fichier spécifique
pytest tests/test_nihilManager.py

# Avec verbose
pytest -v

# Avec couverture (si installé)
pytest --cov=nihil
```

## Notes

Les tests mockent le client Docker, donc **Docker n'a pas besoin de tourner** pour exécuter les tests.

Les tests actuels couvrent les cas de base. À compléter selon les besoins :
- Plus de cas limites pour `create_container` (volumes multiples, user_resources, etc.)
- Tests pour `list_images`, `remove_image` avec différents cas d'erreur
- Tests pour `start_container`, `stop_container`, `remove_container`
- Tests d'intégration si nécessaire
