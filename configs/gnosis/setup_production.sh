#!/bin/bash

# Production Setup Script for CoW Protocol with Balancer Solver - GNOSIS CHAIN
# This script sets up and runs the driver and solver for production competition on Gnosis Chain

set -e

# Production Configuration for Gnosis Chain
NODE_URL="http://91.210.227.29:8545"  # Production RPC endpoint
ORDERBOOK_URL="https://api.cow.fi/xdai/api"  # Production Gnosis orderbook
DRIVER_PORT="11088"
SOLVER_PORT="8080"
CHAIN_NAME="gnosis"

echo "🚀 Setting up CoW Protocol Production Environment - GNOSIS CHAIN"
echo "==========================================================="
echo "Chain: $CHAIN_NAME"
echo "RPC URL: $NODE_URL"
echo "Orderbook URL: $ORDERBOOK_URL"
echo "Driver Port: $DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""

# ⚠️  IMPORTANT PRODUCTION WARNINGS
echo "⚠️  PRODUCTION WARNINGS:"
echo "   - This script connects to PRODUCTION orderbook"
echo "   - Solutions will compete with real funds"
echo "   - Ensure your private key has sufficient funds"
echo "   - Monitor gas costs and RPC usage"
echo "   - Backup your private key securely"
echo ""

# Ask for confirmation
read -p "Are you sure you want to continue with PRODUCTION setup? (yes/no): " confirm
if [[ $confirm != "yes" ]]; then
    echo "❌ Production setup cancelled"
    exit 1
fi

# Check if we're in the right directory
if [ ! -d "services" ]; then
    echo "❌ Error: Please run this script from the root directory (where 'services' folder is located)"
    exit 1
fi

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Error: Rust/Cargo is not installed. Please install Rust first: https://rustup.rs/"
    exit 1
fi

echo "✅ Rust/Cargo is installed"

# Setup gnosis configuration
echo "🔧 Setting up gnosis configuration..."
ln -sf configs/gnosis/driver.toml driver.config.toml
ln -sf configs/gnosis/baseline.toml baseline.config.toml

echo "✅ Gnosis configuration loaded"

# Change to services directory
cd services

echo ""
echo "📦 Building CoW Protocol services..."
cargo build --release

echo ""
echo "🔧 Starting production components..."

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down production services..."
    kill $DRIVER_PID $SOLVER_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the baseline solver
echo "🔧 Starting baseline solver on port $SOLVER_PORT..."
cargo run -p solvers -- --addr 127.0.0.1:$SOLVER_PORT baseline --config ../baseline.config.toml &
SOLVER_PID=$!

# Wait a moment for solver to start
sleep 5

# Start the driver (production mode - no autopilot, direct orderbook connection)
echo "🔧 Starting driver on port $DRIVER_PORT..."
cargo run -p driver -- --config ../driver.config.toml --ethrpc "$NODE_URL" &
DRIVER_PID=$!

echo ""
echo "✅ Production services started successfully for GNOSIS CHAIN!"
echo ""
echo "📊 Production Service Status:"
echo "   - Chain: $CHAIN_NAME"
echo "   - Baseline Solver: http://localhost:$SOLVER_PORT"
echo "   - Driver: http://localhost:$DRIVER_PORT"
echo "   - Orderbook: $ORDERBOOK_URL (PRODUCTION)"
echo ""
echo "🔍 Monitor logs above to see auction activity"
echo "💰 Your solver is now competing in PRODUCTION!"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Production monitoring tips
echo "📈 Production Monitoring Tips:"
echo "   - Watch for successful solution submissions"
echo "   - Monitor gas usage and costs"
echo "   - Check solver balance for settlement payments"
echo "   - Monitor RPC rate limits"
echo ""

# Wait for all background processes
wait

