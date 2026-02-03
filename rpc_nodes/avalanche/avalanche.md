# Avalanche Node Setup Guide

This guide provides step-by-step instructions for setting up an Avalanche node using the binary installation method.

## System Preparation

Update your system and install essential packages:

```bash
apt update && apt upgrade -y
apt install -y curl wget git jq htop ufw tmux
```

## Install AvalancheGo

Add the official APT repository and install:

```bash
wget -qO - https://downloads.avax.network/avalanchego.gpg.key | sudo tee /etc/apt/trusted.gpg.d/avalanchego.asc
source /etc/os-release && echo "deb https://downloads.avax.network/apt $UBUNTU_CODENAME main" | sudo tee /etc/apt/sources.list.d/avalanche.list
sudo apt update
sudo apt install -y avalanchego
```

## Directory Setup

Create the working directory:

```bash
mkdir -p $HOME/.avalanchego
```

## Run the Node

Start a tmux session and run the Avalanche node:

```bash
tmux new -s avalanche
```

Inside the tmux session, start the node with custom ports:

```bash
avalanchego \
  --http-port=8549 \
  --staking-port=30307 \
  --http-host=0.0.0.0 \
  --api-admin-enabled=true \
  --api-metrics-enabled=true \
  --public-ip=<PUBLIC_IP>

# Detach: Ctrl+B then d
# Reattach: tmux attach -t avalanche
```

Replace `YOUR_PUBLIC_IP` with your node's public IP address.

## Firewall Configuration

Ensure the following ports are open:

```bash
sudo ufw allow 8549/tcp   # HTTP API and WebSocket (same port)
sudo ufw allow 30307/tcp  # P2P/Staking
sudo ufw reload
```

## Monitor and Manage

Follow the logs in the tmux session:

```bash
tmux attach -t avalanche
```

### Check Node Health

Check if the node is healthy (should return 200 OK):

```bash
curl http://localhost:8549/ext/health
```

### Check if Node is Bootstrapped

Check if the C-Chain is bootstrapped:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"info.isBootstrapped","params":{"chain":"C"},"id":1}' \
  http://localhost:8549/ext/info
```

### Check Block Height

Get the current C-Chain block height:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8549/ext/bc/C/rpc
```

The response will include a hex block number. To convert to decimal:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8549/ext/bc/C/rpc | jq -r '.result' | xargs printf "%d\n"
```

### Check Node Info

Get general node information:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"info.getNodeVersion","params":[],"id":1}' \
  http://localhost:8549/ext/info
```

## Notes

- Initial sync can take several hours to days depending on hardware and network speed
- The node requires significant storage space (~1TB+ for full node)
- Hardware recommendations: 8+ cores, 16GB RAM (32GB recommended), NVMe SSD
- The P2P port (30307) must be publicly accessible for proper network participation
- WebSocket is available on the same port as HTTP: `ws://localhost:8549/ext/bc/C/ws`

## References

- [Avalanche Node Documentation](https://docs.avax.network/nodes/)
- [AvalancheGo GitHub Repository](https://github.com/ava-labs/avalanchego)
- [Avalanche Builder Hub](https://build.avax.network/docs/nodes/run-a-node)
