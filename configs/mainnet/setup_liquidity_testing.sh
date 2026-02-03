#!/bin/bash

# Independent Liquidity Testing Setup Script for CoW Protocol with Balancer Solver - MAINNET
# This script sets up and runs the autopilot, driver (NO LIQUIDITY), liquidity-driver, and balancer solver

set -e

# Configuration for Mainnet
NODE_URL="http://decentralix.internet-box.ch:8545"  # Replace with your mainnet RPC
ORDERBOOK_URL="https://barn.api.cow.fi/mainnet"  # Staging mainnet orderbook
DRIVER_PORT="11088"
LIQUIDITY_DRIVER_PORT="8080"  # Liquidity-driver port
SOLVER_PORT="8081"
CHAIN_NAME="mainnet"

echo "🚀 Setting up CoW Protocol Independent Liquidity Testing - MAINNET"
echo "============================================================="
echo "Chain: $CHAIN_NAME"
echo "RPC URL: $NODE_URL"
echo "Orderbook URL: $ORDERBOOK_URL"
echo "Driver Port: $DRIVER_PORT (NO LIQUIDITY)"
echo "Liquidity-Driver Port: $LIQUIDITY_DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""
echo "🔄 Architecture:"
echo "   CoW Driver (no liquidity) → Balancer-Solver → Liquidity-Driver (all liquidity)"
echo ""

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

# Setup mainnet configuration
echo "🔧 Setting up mainnet configuration..."
ln -sf configs/mainnet/driver.toml driver.config.toml
ln -sf configs/mainnet/baseline.toml baseline.config.toml
ln -sf configs/mainnet/liquidity-driver.toml liquidity-driver.config.toml

echo "✅ Mainnet configuration loaded"

# Change to services directory
cd services

echo ""
echo "📦 Building CoW Protocol services..."
cargo build --release --bin balancer-solver --bin driver --bin liquidity-driver --bin autopilot

echo ""
echo "🔧 Starting components in correct order..."

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $AUTOPILOT_PID $DRIVER_PID $LIQUIDITY_DRIVER_PID $SOLVER_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Step 1: Start the liquidity-driver (provides ALL liquidity data)
echo "🔧 [1/4] Starting liquidity-driver on port $LIQUIDITY_DRIVER_PORT..."
cargo run -p liquidity-driver -- --config ../liquidity-driver.config.toml --ethrpc "$NODE_URL" --bind 0.0.0.0:$LIQUIDITY_DRIVER_PORT &
LIQUIDITY_DRIVER_PID=$!

# Wait for liquidity-driver to start
sleep 5
echo "✅ Liquidity-driver started"

# Step 2: Start the balancer solver (will call liquidity-driver for data)
echo "🔧 [2/4] Starting balancer solver on port $SOLVER_PORT..."
cargo run -p balancer-solver -- --addr 127.0.0.1:$SOLVER_PORT baseline --config ../baseline.config.toml &
SOLVER_PID=$!

# Wait for solver to start  
sleep 3
echo "✅ Balancer-solver started"

# Step 3: Start the driver (NO liquidity sources configured)
echo "🔧 [3/4] Starting driver on port $DRIVER_PORT..."
cargo run -p driver -- --config ../driver.config.toml --ethrpc "$NODE_URL" &
DRIVER_PID=$!

# Wait for driver to start
sleep 3
echo "✅ Driver started"

# Step 4: Start the autopilot
echo "🔧 [4/4] Starting autopilot..."
cargo run --bin autopilot -- \
    --native-price-estimators "balancer-solver|http://localhost:$DRIVER_PORT/balancer-solver" \
    --skip-event-sync true \
    --node-url "$NODE_URL" \
    --shadow "$ORDERBOOK_URL" \
    --drivers "balancer-solver|http://localhost:$DRIVER_PORT/balancer-solver|0xa0Ee7A142d267C1f36714E4a8F75612F20a79720" &
AUTOPILOT_PID=$!

echo "✅ Autopilot started"

echo ""
echo "✅ All services started successfully for INDEPENDENT LIQUIDITY TESTING!"
echo ""
echo "📊 Service Status:"
echo "   - Chain: $CHAIN_NAME"
echo "   - Liquidity-Driver: http://localhost:$LIQUIDITY_DRIVER_PORT (fetches ALL protocols)"
echo "   - Balancer Solver: http://localhost:$SOLVER_PORT (calls liquidity-driver)"
echo "   - Driver: http://localhost:$DRIVER_PORT (NO liquidity sources)"
echo "   - Autopilot: Running and connected to $ORDERBOOK_URL"
echo ""
echo "🔄 Data Flow:"
echo "   1. CoW Driver receives auction with EMPTY liquidity: []"
echo "   2. Balancer-Solver detects empty liquidity"
echo "   3. Balancer-Solver calls Liquidity-Driver: POST /api/v1/liquidity"
echo "   4. Liquidity-Driver fetches from all protocols (Balancer V2/V3, Uniswap V2/V3)"
echo "   5. Liquidity-Driver returns comprehensive liquidity data"
echo "   6. Balancer-Solver performs routing with fetched data"
echo ""
echo "🧪 Test the API:"
echo "   curl -X POST http://localhost:$LIQUIDITY_DRIVER_PORT/api/v1/liquidity \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"auctionId\":123,\"tokens\":[],\"tokenPairs\":[[\"0xA0b8...\",\"0xC02a...\"]],\"blockNumber\":18000000,\"protocols\":[\"balancer_v2\"]}'"
echo ""
echo "🔍 Monitor logs above to see auction activity and liquidity fetching"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait

