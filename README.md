# Nihil

Docker container manager for pentesting - Inspired by Exegol but simplified.

> 📚 **Documentation complète disponible dans le dossier [`docs/`](docs/README.md)**

## ✨ Fonctionnalités

- 🐳 **Gestion de conteneurs Docker** - Création, démarrage, arrêt automatiques
- 🎨 **Image Arch Linux customisée** - zsh, oh-my-zsh, yay, Chaotic-AUR
- ⌨️ **Auto-complétion** - Support bash et zsh
- 📜 **Historique des commandes** - Fichier texte simple, facile à copier/coller
- 📦 **Dépôt Arch Linux** - Installation automatique des paquets nihil
- 🚀 **Interface CLI intuitive** - Commandes simples et puissantes

## 🚀 Quick Installation

### 1. Build the Docker image

```bash
cd nihil-images
docker build -t nihil:local .
```

### 2. Install Nihil

```bash
cd ..
pipx install -e .
```

## 📖 Usage

### Start a container (automatic creation)
```bash
nihil start my-pentest
```

The container will be created automatically if it doesn't exist, then started and a shell will be opened.

### Start options

**Privileged mode (for network tools):**
```bash
nihil start my-container --privileged
```

**Mount a workspace:**
```bash
nihil start my-container --workspace ~/path/to/folder
```

**Host network mode:**
```bash
nihil start my-container --network host
```

**Start without opening a shell:**
```bash
nihil start my-container --no-shell
```

### Stop a container
```bash
nihil stop my-container
```

### Remove containers
```bash
# Remove a single container
nihil remove my-container

# Remove multiple containers at once
nihil remove container1 container2 container3 --force
```

### Display information
```bash
nihil info
```

Displays:
- Available nihil images
- Existing containers with their status

### Execute a command in a container
```bash
nihil exec my-container
nihil exec my-container ls -la
nihil exec my-container python3 script.py
```

### Auto-complétion
```bash
# Bash
nihil completion bash | sudo tee /etc/bash_completion.d/nihil

# Zsh
nihil completion zsh > ~/.zfunc/_nihil
```

Voir [Auto-complétion](docs/autocompletion.md) pour plus de détails.

### Historique des commandes
Toutes les commandes sont automatiquement enregistrées dans `~/.config/nihil/history.log`.

```bash
# Consulter l'historique
cat ~/.config/nihil/history.log

# Copier-coller une commande directement
```

Voir [Historique](docs/history.md) pour plus de détails.

## 🎯 Usage Examples

### Pentest web

```bash
nihil start pentest-web --workspace ~/projects/pentest-web
# Work in the container...
# Your files in ~/projects/pentest-web are accessible in /workspace
```

### CTF with full network access

```bash
nihil start ctf --privileged --network host
```

### Lightweight container for scripting

```bash
nihil start scripts --workspace ~/scripts --no-shell
nihil exec scripts python3 my-script.py
```

## 📁 Project Architecture

```
nihil/
├── nihil.py                   # Entry point
├── pyproject.toml             # Project configuration
├── requirements.txt           # Dependencies
├── README.md                  # This file
├── docs/                      # Documentation complète
│   ├── README.md             # Index de la documentation
│   ├── installation.md       # Guide d'installation
│   ├── usage.md              # Guide d'utilisation
│   ├── docker-image.md       # Documentation de l'image
│   ├── autocompletion.md     # Auto-complétion
│   ├── history.md            # Historique des commandes
│   ├── arch-repo.md          # Dépôt Arch Linux
│   ├── development.md        # Guide de développement
│   └── faq.md                # Questions fréquentes
└── nihil/
    ├── __init__.py           # Version and metadata
    ├── nihilController.py    # Main controller with CLI
    ├── nihilManager.py       # Docker management
    ├── nihilHelp.py          # CLI parser
    ├── nihilFormatter.py     # Output formatting
    ├── nihilError.py         # Error handling
    ├── nihilDoctor.py        # Diagnostics
    └── nihilHistory.py       # Command history
```

## 🔧 Available Commands

### start
Start a container (creates it automatically if it doesn't exist)

```bash
nihil start <name> [options]
  --privileged       Privileged mode (full network access)
  --network <mode>   Network mode (e.g., host)
  --workspace <path> Mount a working directory
  --no-shell         Don't open shell after starting
```

### stop
Stop a running container

```bash
nihil stop <name>
```

### exec
Execute a command in a container

```bash
nihil exec <name> [command]
# Default: zsh
```

### completion
Generate shell completion script

```bash
nihil completion <bash|zsh>
```

### doctor
Run diagnostics checks

```bash
nihil doctor
```

### uninstall
Remove nihil images

```bash
nihil uninstall [image1 image2 ...] [--force]
```

### remove
Remove one or more containers

```bash
nihil remove <name> [name2 name3 ...] [--force]
```

### info
Display available images and containers

```bash
nihil info
```

## 🛠️ Configuration

### Environment Variables

- `DOCKER_HOST`: Docker host (default: local Unix socket)

### Image Customization

Modify `nihil-images/build/modules/` to add custom installation modules.

## 🔥 Tips

### Quick cleanup of multiple containers
```bash
nihil remove test1 test2 test3 --force
```

### Persistent workspace
```bash
# Your files in ~/my-project are preserved even after container removal
nihil start project --workspace ~/my-project
```
## 📚 Documentation complète

Pour plus de détails, consultez la [documentation complète](docs/README.md) :

- [Installation](docs/installation.md) - Guide d'installation détaillé
- [Utilisation](docs/usage.md) - Toutes les commandes et options
- [Image Docker](docs/docker-image.md) - Personnalisation de l'image
- [Auto-complétion](docs/autocompletion.md) - Configuration bash/zsh
- [Historique](docs/history.md) - Utilisation de l'historique
- [Dépôt Arch](docs/arch-repo.md) - Utilisation du dépôt nihil
- [Développement](docs/development.md) - Guide pour développeurs
- [FAQ](docs/faq.md) - Questions fréquentes

## 🤝 Authors

- **0xbbuddha**
- **Goultarde**

## 📄 License

MIT License - Voir le fichier LICENSE pour plus de détails.
