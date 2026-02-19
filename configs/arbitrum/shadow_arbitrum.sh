#!/bin/bash

# Shadow Competition Script for Balancer Solver - ARBITRUM ONE
# This script runs only the balancer solver for CoW Protocol shadow competition on Arbitrum One

set -e

# Configuration for Arbitrum Shadow Competition
SOLVER_PORT="8101"
SOLVER_HOST="0.0.0.0"  # Bind to all interfaces for external access
CHAIN_NAME="Arbitrum One"
CHAIN_ID="42161"
CONFIG_FILE="baseline.toml"

echo "🏆 Starting Balancer Solver for Shadow Competition - ARBITRUM ONE"
echo "============================================================="
echo "Chain: $CHAIN_NAME (Chain ID: $CHAIN_ID)"
echo "Solver Endpoint: http://$SOLVER_HOST:$SOLVER_PORT"
echo "Config: $CONFIG_FILE"
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

echo "✅ Services directory: $SERVICES_DIR"

# Change to services directory
cd "$SERVICES_DIR"

echo ""
echo "📦 Building balancer solver (release mode)..."
cargo build --release -p balancer-solver

echo ""
echo "🚀 Starting balancer solver for arbitrum shadow competition..."

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down balancer solver..."
    kill $SOLVER_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the balancer solver
echo "🔧 Starting balancer solver on $SOLVER_HOST:$SOLVER_PORT..."
cargo run --release -p balancer-solver -- \
    --log "info,balancer_solver=debug,shared=debug,solver=debug" \
    --addr "$SOLVER_HOST:$SOLVER_PORT" \
    baseline \
    --config "$CONFIG_DIR/baseline.toml" &

SOLVER_PID=$!

# Wait a moment for solver to start
sleep 3

# Check if solver is running
if ! kill -0 $SOLVER_PID 2>/dev/null; then
    echo "❌ Error: Solver failed to start"
    exit 1
fi

echo ""
echo "✅ Balancer solver started successfully for ARBITRUM shadow competition!"
echo ""
echo "📊 Service Information:"
echo "   - Chain: $CHAIN_NAME"
echo "   - Solver Endpoint: http://$SOLVER_HOST:$SOLVER_PORT"
echo "   - Health Check: http://$SOLVER_HOST:$SOLVER_PORT/health"
echo "   - Process ID: $SOLVER_PID"
echo ""
echo "🔗 Provide this endpoint to the CoW team:"
echo "   Solver Name: balancer-solver"
echo "   Arbitrum Endpoint: http://YOUR_PUBLIC_IP:$SOLVER_PORT"
echo "   Chain: arbitrum (Chain ID: 42161)"
echo ""
echo "⚠️  Make sure your firewall allows inbound connections on port $SOLVER_PORT"
echo "💡 Test with: curl http://localhost:$SOLVER_PORT/health"
echo ""
echo "🔍 Monitor logs above for solver activity"
echo "🛑 Press Ctrl+C to stop the solver"
echo ""

# Wait for the solver process
wait $SOLVER_PID
