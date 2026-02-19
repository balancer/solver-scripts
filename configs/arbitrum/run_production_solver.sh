#!/bin/bash

# Production Balancer Solver with Independent Liquidity - ARBITRUM ONE
# ===================================================================
# This script runs the production solver architecture:
# - liquidity-driver: Fetches all liquidity data
# - balancer-solver: Solves auctions using liquidity from liquidity-driver
#
# CoW Protocol runs separately: autopilot + driver (without liquidity)

set -euo pipefail

# Configuration
CHAIN="arbitrum"
CHAIN_ID="42161"
RPC_URL="http://localhost:8547"
LIQUIDITY_DRIVER_PORT="8081"
SOLVER_PORT="8101"

echo "🚀 Starting Production Balancer Solver - ARBITRUM ONE"
echo "====================================================="
echo "Chain: $CHAIN (Chain ID: $CHAIN_ID)"
echo "RPC URL: $RPC_URL"
echo "Liquidity-Driver Port: $LIQUIDITY_DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""
echo "🔄 Architecture:"
echo "   CoW (autopilot + driver) → balancer-solver → liquidity-driver"
echo ""

# Resolve directories from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVICES_DIR="$(cd "$SCRIPTS_ROOT/.." && pwd)/services"
CONFIG_DIR="$SCRIPT_DIR"

# Check prerequisites
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo is not installed"
    exit 1
fi
echo "✅ Rust/Cargo is installed"

# Check if services directory exists as sibling
if [ ! -d "$SERVICES_DIR" ]; then
    echo "❌ Error: 'services' directory not found at $SERVICES_DIR"
    echo "   Expected directory layout: services/ and solver-scripts/ side by side"
    exit 1
fi

echo "✅ Services directory: $SERVICES_DIR"

# Build services
echo ""
echo "📦 Building production services..."
cd "$SERVICES_DIR"
cargo build --release --bin liquidity-driver --bin balancer-solver

echo ""
echo "🚀 Starting services in production mode..."
echo ""

# Create logs directory in scripts root
LOGS_DIR="$SCRIPTS_ROOT/logs"
mkdir -p "$LOGS_DIR"

# Start liquidity-driver
echo "Starting liquidity-driver on port $LIQUIDITY_DRIVER_PORT..."
RUST_LOG=trace cargo run --release --bin liquidity-driver -- \
    --ethrpc "$RPC_URL" \
    --config "$CONFIG_DIR/liquidity-driver.toml" \
    --addr "0.0.0.0:$LIQUIDITY_DRIVER_PORT" >> "$LOGS_DIR/liquidity-driver-$CHAIN.log" 2>&1 &

LIQUIDITY_DRIVER_PID=$!
echo "✅ liquidity-driver started (PID: $LIQUIDITY_DRIVER_PID)"

# Wait for liquidity-driver to start
echo "⏳ Waiting for liquidity-driver to initialize..."
sleep 10

# Test liquidity-driver health
if curl -f -s "http://localhost:$LIQUIDITY_DRIVER_PORT/health" > /dev/null; then
    echo "✅ liquidity-driver is healthy"
else
    echo "⚠️  liquidity-driver health check failed, but continuing..."
fi

# Start balancer-solver (needs baseline subcommand)
echo ""
echo "Starting balancer-solver on port $SOLVER_PORT..."
# Log filter: debug for solver, info for HTTP layer, warn for everything else
# Change to LOG=trace for full verbose logging if needed
LOG="balancer_solver=debug,tower_http=info,reqwest=info,warn" cargo run --release --bin balancer-solver -- \
    --addr "0.0.0.0:$SOLVER_PORT" \
    baseline --config "$CONFIG_DIR/baseline.toml" >> "$LOGS_DIR/balancer-solver-$CHAIN.log" 2>&1 &

SOLVER_PID=$!
echo "✅ balancer-solver started (PID: $SOLVER_PID)"

# Wait for solver to start
echo "⏳ Waiting for balancer-solver to initialize..."
sleep 5

# Test solver health
if curl -f -s "http://localhost:$SOLVER_PORT/health" > /dev/null; then
    echo "✅ balancer-solver is healthy"
else
    echo "⚠️  balancer-solver health check failed, but continuing..."
fi

echo ""
echo "🎯 Production Balancer Solver is running!"
echo "=========================================="
echo "Liquidity-Driver: http://localhost:$LIQUIDITY_DRIVER_PORT"
echo "Balancer-Solver:  http://localhost:$SOLVER_PORT"
echo ""
echo "To stop services:"
echo "  kill $LIQUIDITY_DRIVER_PID $SOLVER_PID"
echo ""
echo "Logs:"
echo "  liquidity-driver: $LOGS_DIR/liquidity-driver-$CHAIN.log (PID $LIQUIDITY_DRIVER_PID)"
echo "  balancer-solver:  $LOGS_DIR/balancer-solver-$CHAIN.log (PID $SOLVER_PID)"
echo ""
echo "To tail logs in real-time:"
echo "  tail -f $LOGS_DIR/liquidity-driver-$CHAIN.log"
echo "  tail -f $LOGS_DIR/balancer-solver-$CHAIN.log"
echo ""

# Keep script running and handle shutdown gracefully
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $LIQUIDITY_DRIVER_PID $SOLVER_PID 2>/dev/null || true
    wait $LIQUIDITY_DRIVER_PID $SOLVER_PID 2>/dev/null || true
    echo "✅ Services stopped"
}

trap cleanup EXIT
trap cleanup INT
trap cleanup TERM

# Wait for processes
wait $LIQUIDITY_DRIVER_PID $SOLVER_PID
