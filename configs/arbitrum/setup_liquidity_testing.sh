#!/bin/bash

# Independent Liquidity Testing Setup Script for CoW Protocol with Balancer Solver - ARBITRUM ONE
# This script sets up and runs the autopilot, driver (NO LIQUIDITY), liquidity-driver, and balancer solver

set -e

# Configuration for Arbitrum One
NODE_URL="https://arb1.arbitrum.io/rpc"  # Arbitrum One RPC
ORDERBOOK_URL="https://barn.api.cow.fi/arbitrum_one"  # Staging arbitrum orderbook
DRIVER_PORT="11088"
LIQUIDITY_DRIVER_PORT="8081"  # Liquidity-driver port (matches baseline.toml)
SOLVER_PORT="8082"
CHAIN_NAME="arbitrum"

# Resolve directories from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVICES_DIR="$(cd "$SCRIPTS_ROOT/.." && pwd)/services"
CONFIG_DIR="$SCRIPT_DIR"

echo "🚀 Setting up CoW Protocol Independent Liquidity Testing - ARBITRUM ONE"
echo "============================================================="
echo "Chain: $CHAIN_NAME (Chain ID: 42161)"
echo "RPC URL: $NODE_URL"
echo "Orderbook URL: $ORDERBOOK_URL"
echo "Driver Port: $DRIVER_PORT (NO LIQUIDITY)"
echo "Liquidity-Driver Port: $LIQUIDITY_DRIVER_PORT"
echo "Solver Port: $SOLVER_PORT"
echo ""
echo "🔄 Architecture:"
echo "   CoW Driver (no liquidity) → Balancer-Solver → Liquidity-Driver (all liquidity)"
echo ""

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
cargo run --release --bin liquidity-driver -- --config "$CONFIG_DIR/liquidity-driver.toml" --ethrpc "$NODE_URL" --addr 0.0.0.0:$LIQUIDITY_DRIVER_PORT &
LIQUIDITY_DRIVER_PID=$!

# Wait for liquidity-driver to start
sleep 5
echo "✅ Liquidity-driver started"

# Step 2: Start the balancer solver (will call liquidity-driver for data)
echo "🔧 [2/4] Starting balancer solver on port $SOLVER_PORT..."
cargo run -p balancer-solver -- --addr 127.0.0.1:$SOLVER_PORT baseline --config "$CONFIG_DIR/baseline.toml" &
SOLVER_PID=$!

# Wait for solver to start  
sleep 3
echo "✅ Balancer-solver started"

# Step 3: Start the driver (NO liquidity sources configured)
echo "🔧 [3/4] Starting driver on port $DRIVER_PORT..."
cargo run -p driver -- --config "$CONFIG_DIR/driver.toml" --ethrpc "$NODE_URL" &
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
echo "✅ All services started successfully for ARBITRUM INDEPENDENT LIQUIDITY TESTING!"
echo ""
echo "📊 Service Status:"
echo "   - Chain: $CHAIN_NAME (Chain ID: 42161)"
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
echo "     -d '{\"auctionId\":123,\"tokens\":[],\"tokenPairs\":[[\"0x82aF...\",\"0xFF97...\"]],\"blockNumber\":18000000,\"protocols\":[\"balancer_v2\"]}'"
echo ""
echo "🔍 Monitor logs above to see auction activity and liquidity fetching"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait



