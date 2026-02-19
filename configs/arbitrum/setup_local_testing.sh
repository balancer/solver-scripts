#!/bin/bash

# Local Testing Setup Script for CoW Protocol with Balancer Solver - ARBITRUM ONE
# This script sets up and runs the autopilot, driver, and balancer solver for Arbitrum One

set -e

# Configuration for Arbitrum One
NODE_URL="http://decentralix.internet-box.ch:8547"  # Replace with your Arbitrum RPC
ORDERBOOK_URL="https://barn.api.cow.fi/arbitrum_one"  # Staging Arbitrum orderbook
DRIVER_PORT="11088"
SOLVER_PORT="8082"
CHAIN_NAME="arbitrum"

echo "🚀 Setting up CoW Protocol Local Testing Environment - ARBITRUM ONE"
echo "=================================================================="
echo "Chain: $CHAIN_NAME"
echo "RPC URL: $NODE_URL"
echo "Orderbook URL: $ORDERBOOK_URL"
echo "Driver Port: $DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""

# Resolve directories from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVICES_DIR="$(cd "$SCRIPTS_ROOT/.." && pwd)/services"
CONFIG_DIR="$SCRIPT_DIR"

# Check if services directory exists as sibling
if [ ! -d "$SERVICES_DIR" ]; then
    echo "❌ Error: 'services' directory not found at $SERVICES_DIR"
    echo "   Expected directory layout: services/ and solver-scripts/ side by side"
    exit 1
fi

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Error: Rust/Cargo is not installed. Please install Rust first: https://rustup.rs/"
    exit 1
fi

echo "✅ Rust/Cargo is installed"
echo "✅ Services directory: $SERVICES_DIR"

# Change to services directory
cd "$SERVICES_DIR"

echo ""
echo "📦 Building CoW Protocol services..."
cargo build --release

echo ""
echo "🔧 Starting components..."

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $AUTOPILOT_PID $DRIVER_PID $SOLVER_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the balancer solver
echo "🔧 Starting balancer solver on port $SOLVER_PORT..."
cargo run -p balancer-solver -- --addr 127.0.0.1:$SOLVER_PORT baseline --config "$CONFIG_DIR/baseline.toml" &
SOLVER_PID=$!

# Wait a moment for solver to start
sleep 3

# Start the driver
echo "🔧 Starting driver on port $DRIVER_PORT..."
cargo run -p driver -- --config "$CONFIG_DIR/driver.toml" --ethrpc "$NODE_URL" &
DRIVER_PID=$!

# Wait a moment for driver to start
sleep 3

# Start the autopilot
echo "🔧 Starting autopilot..."
cargo run --bin autopilot -- \
    --native-price-estimators "balancer-solver|http://localhost:$DRIVER_PORT/balancer-solver" \
    --skip-event-sync true \
    --node-url "$NODE_URL" \
    --shadow "$ORDERBOOK_URL" \
    --drivers "balancer-solver|http://localhost:$DRIVER_PORT/balancer-solver|0xa0Ee7A142d267C1f36714E4a8F75612F20a79720" &
AUTOPILOT_PID=$!

echo ""
echo "✅ All services started successfully for ARBITRUM ONE!"
echo ""
echo "📊 Service Status:"
echo "   - Chain: $CHAIN_NAME"
echo "   - Balancer Solver: http://localhost:$SOLVER_PORT"
echo "   - Driver: http://localhost:$DRIVER_PORT"
echo "   - Autopilot: Running and connected to $ORDERBOOK_URL"
echo ""
echo "🔍 Monitor logs above to see auction activity"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait 