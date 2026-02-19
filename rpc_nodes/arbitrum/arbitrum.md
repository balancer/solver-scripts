# Arbitrum Nitro Node Setup Guide

This guide provides step-by-step instructions for setting up an Arbitrum One (Nitro) node using Docker and a pruned snapshot.

## Directory Setup

Create the working directory:

```bash
mkdir $HOME/arbitrum
chmod -R 777 $HOME/arbitrum
cd $HOME/arbitrum
```

## Download Snapshot

Check [Arbitrum Snapshots](https://snapshot-explorer.arbitrum.io/?chain=arb1) for the latest available snapshots.

Install aria2 and start a tmux session for the download:

```bash
apt install -y aria2
tmux new -s arbitrum
```

Download the pruned snapshot parts:

```bash
aria2c -Z -x 16 \
  "https://snapshot.arbitrum.io/arb1/2026-01-28-e838b4ee/pruned.tar.part0000" \
  "https://snapshot.arbitrum.io/arb1/2026-01-28-e838b4ee/pruned.tar.part0001" \
  "https://snapshot.arbitrum.io/arb1/2026-01-28-e838b4ee/pruned.tar.part0002" \
  "https://snapshot.arbitrum.io/arb1/2026-01-28-e838b4ee/pruned.tar.part0003"

# Detach: Ctrl+B then d
# Reattach: tmux attach -t arbitrum
```

## Concatenate Snapshot

Combine the parts into a single tar file:

```bash
cat pruned.tar.part* > pruned.tar
```

After concatenation, remove the part files:

```bash
rm -f pruned.tar.part*
```

## Environment Setup

Create a `.env` file to store your RPC endpoints securely:

```bash
nano $HOME/arbitrum/.env
```

Add your DRPC endpoints:

```
ETH_L1_RPC=https://your-drpc-eth-mainnet-endpoint
ETH_BEACON_RPC=https://your-drpc-beacon-endpoint
```

Lock file permissions:

```bash
chmod 600 $HOME/arbitrum/.env
```

## Run the Node

Load the environment variables and start the Arbitrum Nitro node with Docker:

```bash
source $HOME/arbitrum/.env

docker run --stop-timeout 300 --name arbitrum -d --restart unless-stopped \
  -v $HOME/arbitrum:/home/user/.arbitrum \
  -p 0.0.0.0:8547:8547 \
  -p 0.0.0.0:8548:8548 \
  offchainlabs/nitro-node:v3.9.5-66e42c4 \
  --parent-chain.connection.url $ETH_L1_RPC \
  --parent-chain.blob-client.beacon-url $ETH_BEACON_RPC \
  --chain.id=42161 \
  --http.api=net,web3,eth,debug \
  --http.corsdomain=* \
  --http.addr=0.0.0.0 \
  --http.vhosts=* \
  --ws.origins=* \
  --ws.port=8548 \
  --ws.addr=0.0.0.0 \
  --node.staker.enable=false \
  --init.url="file:///home/user/.arbitrum/pruned.tar" \
  --init.prune=minimal                                  # Optional: prune to minimize disk space (only use this flag after initial launch!)
```

Optional init flags (uncomment on first run):
- `--init.url` - Initialize from the local snapshot file
- `--init.prune` - Prune database on startup (`minimal` = least disk space, `full`, or `validator`)

> **Note:** After initialization completes, remove the tar file with `rm -f $HOME/arbitrum/pruned.tar`

## Monitor and Manage

Follow the logs to monitor sync progress:

```bash
docker logs -f --tail 100 arbitrum
```

Gracefully stop the node (allows time to flush state):

```bash
docker stop --timeout=300 arbitrum
```
