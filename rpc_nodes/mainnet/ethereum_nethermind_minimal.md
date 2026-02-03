# Ethereum Nethermind Minimal Node Setup Guide

This guide provides step-by-step instructions for setting up a minimal Ethereum mainnet node using Nethermind as the execution client and Lodestar as the consensus client, with aggressive pruning for lowest storage requirements.

## System Requirements

A minimal pruned node has lower requirements than an archive node:

- **Storage**: Minimum 1 TB SSD (keep 500GB free for pruning headroom)
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

Create the working directories for Ethereum data:

```bash
mkdir -p $HOME/ethereum/execution
mkdir -p $HOME/ethereum/consensus
mkdir -p $HOME/ethereum/jwt
chown -R 1000:1000 $HOME/ethereum/
```

## Generate JWT Secret

Create a JWT secret file for secure communication between execution and consensus clients:

```bash
openssl rand -hex 32 > $HOME/ethereum/jwt/jwt.hex
```

## Docker Compose Setup

Use the provided template at `nodes/ethereum_nethermind_minimal/docker-compose.yml`, then adjust as needed:

```bash
cd $HOME/ethereum
nano docker-compose.yml
```

Key configuration in the compose file:

- **Pruning Mode**: Set to `Full` for automatic state pruning
- **Pruning Trigger**: Auto-prunes when state DB exceeds 500GB
- **Volume paths**: Point to storage with at least 1TB available
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
  http://localhost:8546
```

Or check the latest block:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8546
```

Check Lodestar beacon sync status:

```bash
curl http://localhost:5053/eth/v1/node/syncing
```

## Notes

- Initial sync is faster than archive mode due to snap sync
- **Full pruning process takes 30-50 hours** and is resource intensive (high CPU, memory, disk I/O)
- Cannot query old historical state - only recent blocks are available
- Auto-pruning triggers when state DB exceeds 500GB threshold
- Keep at least 500GB free disk space for pruning headroom
- During pruning, node performance may be degraded
- Lodestar uses checkpoint sync for fast beacon chain synchronization

## References

- [Nethermind Documentation](https://docs.nethermind.io/)
- [Nethermind Pruning Guide](https://docs.nethermind.io/fundamentals/pruning/)
- [Lodestar Documentation](https://chainsafe.github.io/lodestar/)
- [Ethereum Node Setup](https://ethereum.org/en/developers/docs/nodes-and-clients/run-a-node/)
- [Lodestar Checkpoint Sync](https://beaconstate-mainnet.chainsafe.io/)
