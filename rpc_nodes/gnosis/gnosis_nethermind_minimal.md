# Gnosis Nethermind Minimal Node Setup Guide

This guide provides step-by-step instructions for setting up a minimal Gnosis Chain node using Nethermind as the execution client and Lodestar as the consensus client, with aggressive pruning for lowest storage requirements.

## System Requirements

A minimal pruned node has lower requirements than an archive node:

- **Storage**: Minimum 500 GB SSD (keep 300GB free for pruning headroom)
- **RAM**: 8 GB minimum
- **CPU**: Dual-core processor or better
- **Network**: Stable broadband connection

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

Create the working directories for Gnosis data:

```bash
mkdir -p $HOME/gnosis/execution
mkdir -p $HOME/gnosis/consensus
mkdir -p $HOME/gnosis/jwt
chown -R 1000:1000 $HOME/gnosis/
```

## Generate JWT Secret

Create a JWT secret file for secure communication between execution and consensus clients:

```bash
openssl rand -hex 32 > $HOME/gnosis/jwt/jwt.hex
```

## Docker Compose Setup

Use the provided template at `nodes/gnosis_nethermind_minimal/docker-compose.yml`, then adjust as needed:

```bash
cd $HOME/gnosis
nano docker-compose.yml
```

Key configuration in the compose file:

- **Pruning Mode**: Set to `Full` for automatic state pruning
- **Pruning Trigger**: Auto-prunes when state DB exceeds 300GB
- **Volume paths**: Point to storage with at least 500GB available
- **Ports**: Adjust if running multiple nodes on the same machine

## Run the Node

Pull the images, start the services, and follow logs:

```bash
docker compose pull
docker compose up -d
docker compose logs -f --tail 100
```

## Verify Sync Status

Check sync progress via JSON-RPC:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' \
  http://localhost:8545
```

Or check the latest block:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8545
```

Check Lodestar beacon sync status:

```bash
curl http://localhost:5052/eth/v1/node/syncing
```

## Notes

- Initial sync is faster than archive mode due to snap sync
- **Full pruning process takes 20-30 hours** and is resource intensive (high CPU, memory, disk I/O)
- Cannot query old historical state - only recent blocks are available
- Auto-pruning triggers when state DB exceeds 300GB threshold
- Keep at least 300GB free disk space for pruning headroom
- During pruning, node performance may be degraded
- Lodestar uses checkpoint sync for fast beacon chain synchronization

## References

- [Nethermind Documentation](https://docs.nethermind.io/)
- [Nethermind Pruning Guide](https://docs.nethermind.io/fundamentals/pruning/)
- [Lodestar Documentation](https://chainsafe.github.io/lodestar/)
- [Gnosis Chain Node Setup](https://docs.gnosischain.com/node/)
- [Gnosis Checkpoint Sync](https://checkpoint.gnosischain.com/)
