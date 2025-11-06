# Nihil

Docker container manager for pentesting - Inspired by Exegol but simplified.

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
└── nihil/
    ├── __init__.py           # Version and metadata
    ├── controller.py         # Main controller with CLI
    └── docker_manager.py     # Docker management
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
# Default: bash
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
## 🤝 Authors

- 0xbbuddha
- Goultarde
