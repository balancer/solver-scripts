# Polygon Erigon Node Setup Guide

This guide provides step-by-step instructions for setting up a Polygon (Bor) Erigon node from source.

## System Preparation

Update your system and install essential packages:

```bash
apt update && apt upgrade -y

apt install -y curl wget git jq htop ufw
```

## Docker Installation

Remove any existing Docker packages and install Docker from the official repository.

### Remove existing Docker packages (if any):

```bash
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove $pkg
done
```

### Add Docker's official GPG key:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

### Add the repository to Apt sources:

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

### Install Docker:

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## Directory Setup

Create the working directories for Polygon data and set ownership:

```bash
mkdir -p $HOME/polygon/data
chown -R 1000:1000 $HOME/polygon/
```

## Docker Compose Setup

Use the provided template at `nodes/polygon_erigon/docker-compose.yml`, then adjust host paths or ports if needed:

```bash
cd $HOME/polygon
nano docker-compose.yml
```

Key options to review in the compose file:
- Volume path: point the host path to fast storage (e.g., `$HOME/polygon/data` or `/mnt/ssd/polygon-erigon`).
- Prune mode: uncomment either `--prune.mode=archive` or `--prune.mode=minimal` to control state size.
- Optional endpoints: enable `--ws` and/or metrics flags if required.

## Run the Node

Pull the image, start the services, and follow logs:

```bash
docker compose pull 
docker compose up -d --build
docker compose logs -f --tail 100
```
