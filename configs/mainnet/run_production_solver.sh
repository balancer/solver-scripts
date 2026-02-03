#!/bin/bash

# Production Balancer Solver with Independent Liquidity - MAINNET
# =============================================================
# This script runs the production solver architecture:
# - liquidity-driver: Fetches all liquidity data
# - balancer-solver: Solves auctions using liquidity from liquidity-driver
#
# CoW Protocol runs separately: autopilot + driver (without liquidity)

set -euo pipefail

# Configuration
CHAIN="mainnet"
CHAIN_ID="1"
RPC_URL="http://localhost:8546"
LIQUIDITY_DRIVER_PORT="8080"
SOLVER_PORT="8100"

echo "🚀 Starting Production Balancer Solver - MAINNET"
echo "=================================================="
echo "Chain: $CHAIN (Chain ID: $CHAIN_ID)"
echo "RPC URL: $RPC_URL"
echo "Liquidity-Driver Port: $LIQUIDITY_DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""
echo "🔄 Architecture:"
echo "   CoW (autopilot + driver) → balancer-solver → liquidity-driver"
echo ""

# Check prerequisites
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo is not installed"
    exit 1
fi
echo "✅ Rust/Cargo is installed"

# Setup configuration
echo "🔧 Setting up $CHAIN configuration..."
cd "$(dirname "$0")/../.."
CONFIG_DIR="configs/$CHAIN"

# Create symlinks for configuration files
ln -sf "$PWD/$CONFIG_DIR/liquidity-driver.toml" liquidity-driver.config.toml
ln -sf "$PWD/$CONFIG_DIR/baseline.toml" baseline.config.toml

echo "✅ $CHAIN configuration loaded"

# Build services
echo ""
echo "📦 Building production services..."
cd services
cargo build --release --bin liquidity-driver --bin balancer-solver

echo ""
echo "🚀 Starting services in production mode..."
echo ""

# Create logs directory
mkdir -p logs

# Start liquidity-driver (uses standard driver config format)
echo "Starting liquidity-driver on port $LIQUIDITY_DRIVER_PORT..."
RUST_LOG=trace cargo run --release --bin liquidity-driver -- \
    --ethrpc "$RPC_URL" \
    --config ../liquidity-driver.config.toml \
    --addr "0.0.0.0:$LIQUIDITY_DRIVER_PORT" >> ../logs/liquidity-driver-$CHAIN.log 2>&1 &

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
    baseline --config ../baseline.config.toml >> ../logs/balancer-solver-$CHAIN.log 2>&1 &

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
echo "  liquidity-driver: logs/liquidity-driver-$CHAIN.log (PID $LIQUIDITY_DRIVER_PID)"
echo "  balancer-solver:  logs/balancer-solver-$CHAIN.log (PID $SOLVER_PID)"
echo ""
echo "To tail logs in real-time:"
echo "  tail -f logs/liquidity-driver-$CHAIN.log"
echo "  tail -f logs/balancer-solver-$CHAIN.log"
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
