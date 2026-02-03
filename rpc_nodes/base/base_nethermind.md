# Base Nethermind Node Setup Guide

This guide provides step-by-step instructions for setting up a Base Mainnet node using Nethermind with op-node as the consensus client.

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

Create the working directories for Base data:

```bash
mkdir -p $HOME/base/data
mkdir -p $HOME/base/jwt
chown -R 1000:1000 $HOME/base/
```

## Generate JWT Secret

Create a JWT secret file for secure communication:

```bash
openssl rand -hex 32 > $HOME/base/jwt/jwt.hex
```

## Docker Compose Setup

Use the provided template at `nodes/base_nethermind/docker-compose.yml`, then adjust as needed:

```bash
cd $HOME/base
nano docker-compose.yml
```

Key configuration in the compose file:

- **L1_RPC_URL**: Set to your Ethereum Mainnet L1 execution client RPC endpoint
- **L1_BEACON_URL**: Set to your Ethereum Mainnet L1 beacon client endpoint
- **Volume paths**: Point to fast NVMe storage with sufficient space (2TB+ recommended)
- **Ports**: Adjust if running multiple nodes on the same machine

## Run the Node

Pull the image, start the services, and follow logs:

```bash
docker compose pull
docker compose up -d --build
docker compose logs -f --tail 100
```

## Verify Sync Status

Check sync progress via JSON-RPC:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' \
  http://localhost:8540
```

Or check the latest block:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8540
```

## Notes

- Initial sync can take several hours to days depending on hardware and network speed
- Enable `--Sync.SnapSync=true` for faster initial synchronization (enabled by default in recent versions)
- Base requires significant storage space (~2TB+ for full node, 4TB+ for archive)
- Hardware recommendations: 8+ cores, 32GB RAM (64GB recommended), NVMe SSD

## References

- [Nethermind L2 Networks Documentation](https://docs.nethermind.io/get-started/running-node/l2-networks/)
- [Base Node Operators Guide](https://docs.base.org/base-chain/node-operators/)
- [Base Node GitHub Repository](https://github.com/base/node)
