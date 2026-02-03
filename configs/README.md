# Multi-Chain Balancer Solver Configuration

This directory contains configuration files for running Balancer solvers on multiple chains. Each chain has its own directory with specific configuration files and a local testing setup script.

## Directory Structure

```
configs/
├── mainnet/                    # Ethereum Mainnet (Chain ID: 1)
│   ├── driver.toml            # Driver configuration
│   ├── baseline.toml          # Baseline solver configuration
│   ├── liquidity-driver.toml  # Liquidity-driver configuration
│   ├── setup_local_testing.sh # Local testing setup script
│   ├── setup_liquidity_testing.sh # Independent liquidity testing
│   └── run_production_solver.sh   # Production solver script
├── gnosis/                    # Gnosis Chain (Chain ID: 100)
│   ├── driver.toml            # Driver configuration
│   ├── baseline.toml          # Baseline solver configuration
│   ├── liquidity-driver.toml  # Liquidity-driver configuration
│   ├── setup_local_testing.sh # Local testing setup script
│   ├── setup_liquidity_testing.sh # Independent liquidity testing
│   └── run_production_solver.sh   # Production solver script
├── arbitrum/                  # Arbitrum One (Chain ID: 42161)
│   ├── driver.toml
│   ├── baseline.toml
│   ├── liquidity-driver.toml
│   ├── setup_local_testing.sh
│   ├── setup_liquidity_testing.sh
│   └── run_production_solver.sh
├── base/                      # Base (Chain ID: 8453)
│   ├── driver.toml
│   ├── baseline.toml
│   ├── liquidity-driver.toml
│   ├── setup_local_testing.sh
│   ├── setup_liquidity_testing.sh
│   └── run_production_solver.sh
├── polygon/                   # Polygon (Chain ID: 137)
│   ├── driver.toml
│   ├── baseline.toml
│   ├── liquidity-driver.toml
│   ├── setup_local_testing.sh
│   ├── setup_liquidity_testing.sh
│   └── run_production_solver.sh
└── avalanche/                 # Avalanche (Chain ID: 43114)
    ├── driver.toml
    ├── baseline.toml
    ├── liquidity-driver.toml
    ├── setup_local_testing.sh
    ├── setup_liquidity_testing.sh
    └── run_production_solver.sh
```

## Configuration Files

### driver.toml
The main driver configuration file containing:
- Chain ID
- Solver settings (endpoint, slippage, account)
- Contract addresses (GPv2 Settlement, WETH, etc.)
- Order priority strategies
- Submission settings
- **NOTE**: Liquidity sources removed for independent liquidity architecture

### baseline.toml
Baseline solver configuration containing:
- Chain ID
- Base tokens for price estimation
- Routing parameters (max hops, attempts)
- Native token price estimation amount
- **NEW**: Independent liquidity fetching configuration
- **NEW**: `[logging]` toggles for auction files, competition snapshots, swap logs, enhanced solutions, and verification tasks

Example:
```toml
[logging]
auction-files = true              # Save auction/solution JSON
competition = true                # Fetch CoW competition data
swap-logs = true                  # Persist per-swap logs
swap-log-verification = true      # Re-query pools for each swap
solution-verification = true      # Re-verify returned solutions
enhanced-solutions = true         # Persist enhanced solution variants
```
### liquidity-driver.toml (NEW)
Dedicated liquidity-driver configuration containing:
- **CRITICAL**: Must be 1:1 structure with `driver.toml` (liquidity-driver is a copy of driver crate)
- Includes dummy `[[solver]]` and `[submission]` sections (required by config parser, but unused)
- Chain ID and contract addresses
- Base tokens (matches baseline solver)  
- ALL liquidity sources (Balancer V2/V3, Uniswap V2/V3, etc.)
- Protocol-specific settings and graph URLs

**Config Structure Requirements:**
```toml
# These sections are REQUIRED by the config parser (even if unused)
[[solver]]         # Dummy solver config
[submission]       # Dummy submission config

# These sections are ACTUALLY USED for liquidity fetching  
[contracts]        # Contract addresses
[liquidity]        # Liquidity sources and base tokens
[[liquidity.balancer-v2]]  # Protocol configurations
```

### setup_local_testing.sh
Chain-specific local testing script that:
- Sets up the correct configuration files for the chain
- Starts the baseline solver, driver, and autopilot
- Connects to the appropriate staging orderbook
- Provides proper cleanup on exit

### setup_liquidity_testing.sh (NEW)
Independent liquidity testing script that:
- Starts liquidity-driver (with ALL protocol sources)
- Starts baseline solver (calls liquidity-driver for data)
- Starts driver (with NO liquidity sources)
- Starts autopilot
- Tests the new independent liquidity architecture

### run_production_solver.sh (NEW - PRODUCTION)
Production solver script that runs only YOUR components:
- Starts liquidity-driver (port 8080) - fetches all liquidity
- Starts balancer-solver (port 8083) - solves auctions
- Does NOT start autopilot or driver (CoW runs these separately)
- Builds with --release flag for production performance

## Quick Start

### Standard Architecture (Driver with embedded liquidity)
To run local testing with the standard architecture:

```bash
# For Gnosis Chain
./configs/gnosis/setup_local_testing.sh

# For Mainnet
./configs/mainnet/setup_local_testing.sh

# For Arbitrum, Base, Polygon, Avalanche...
./configs/{chain}/setup_local_testing.sh
```

### NEW: Independent Liquidity Architecture
To test the new independent liquidity fetching architecture:

```bash
# For Mainnet - Independent Liquidity Testing
./configs/mainnet/setup_liquidity_testing.sh

# For Gnosis Chain - Independent Liquidity Testing
./configs/gnosis/setup_liquidity_testing.sh

# For all supported chains - Independent Liquidity Testing
./configs/arbitrum/setup_liquidity_testing.sh
./configs/base/setup_liquidity_testing.sh
./configs/polygon/setup_liquidity_testing.sh
./configs/avalanche/setup_liquidity_testing.sh
```

### NEW: Production Solver (Your Components Only)
To run the production solver with independent liquidity (no CoW autopilot/driver):

```bash
# For Mainnet Production
./configs/mainnet/run_production_solver.sh

# For Arbitrum Production
./configs/arbitrum/run_production_solver.sh

# For all supported chains - Production
./configs/gnosis/run_production_solver.sh
./configs/base/run_production_solver.sh
./configs/polygon/run_production_solver.sh
./configs/avalanche/run_production_solver.sh
```

**Production Architecture:**
```
CoW (autopilot + driver) → balancer-solver (port 8083) ↔ liquidity-driver (port 8080)
```

### Architecture Comparison

**Standard Architecture:**
```
CoW Driver (with liquidity) → Balancer-Solver
```

**NEW Independent Architecture:**
```
CoW Driver (NO liquidity) → Balancer-Solver ↔ Liquidity-Driver (ALL liquidity)
```

## Chain-Specific Details

### Ethereum Mainnet (Chain ID: 1)
- **WETH**: `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`
- **RPC**: `http://178.63.49.247:8545` (replace with your mainnet RPC)
- **Orderbook**: `https://barn.api.cow.fi/mainnet/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2`

### Gnosis Chain (Chain ID: 100)
- **WETH**: `0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d` (WXDAI)
- **RPC**: `https://rpc.gnosischain.com`
- **Orderbook**: `https://barn.api.cow.fi/xdai/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2-gnosis-chain`

### Arbitrum One (Chain ID: 42161)
- **WETH**: `0x82aF49447D8a07e3bd95BD0d56f35241523fBab1`
- **RPC**: `https://arb1.arbitrum.io/rpc`
- **Orderbook**: `https://barn.api.cow.fi/arbitrum_one/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2-arbitrum`

### Base (Chain ID: 8453)
- **WETH**: `0x4200000000000000000000000000000000000006`
- **RPC**: `https://mainnet.base.org`
- **Orderbook**: `https://barn.api.cow.fi/base/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2-base`

### Polygon (Chain ID: 137)
- **WETH**: `0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270` (WMATIC)
- **RPC**: `https://polygon-rpc.com`
- **Orderbook**: `https://barn.api.cow.fi/polygon/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2-polygon`

### Avalanche (Chain ID: 43114)
- **WETH**: `0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7` (WAVAX)
- **RPC**: `https://api.avax.network/ext/bc/C/rpc`
- **Orderbook**: `https://barn.api.cow.fi/avalanche/api`
- **Balancer V2 Subgraph**: `https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2-avalanche`

## What Each Setup Script Does

### setup_local_testing.sh (Standard Architecture)
1. **Configuration Setup**: Links the appropriate `driver.toml` and `baseline.toml` files
2. **Service Building**: Builds the CoW Protocol services with `cargo build --release`
3. **Component Startup**: Starts three services in sequence:
   - **Baseline Solver**: Runs on port 8080
   - **Driver**: Runs on port 11088
   - **Autopilot**: Connects to the staging orderbook
4. **Cleanup**: Properly shuts down all services on Ctrl+C

### setup_liquidity_testing.sh (Independent Liquidity Architecture)
1. **Configuration Setup**: Links `liquidity-driver.toml` and updated `baseline.toml`
2. **Service Building**: Builds all services including the new `liquidity-driver`
3. **Component Startup**: Starts four services in sequence:
   - **Liquidity-Driver**: Runs on port 8080 (fetches all liquidity)
   - **Balancer-Solver**: Runs on port 8083 (calls liquidity-driver)
   - **Driver**: Runs on port 11088 (NO liquidity sources)
   - **Autopilot**: Connects to the staging orderbook
4. **Health Checks**: Tests API connectivity between services
5. **Cleanup**: Properly shuts down all services on Ctrl+C

### run_production_solver.sh (Production - Your Components Only)
1. **Configuration Setup**: Links production configuration files
2. **Production Building**: Builds services with `--release` flag for optimal performance
3. **Component Startup**: Starts TWO production services:
   - **Liquidity-Driver**: Port 8080 (your liquidity fetching service)
   - **Balancer-Solver**: Port 8083 (your solver service)
4. **Health Monitoring**: Continuous health checks and graceful error handling
5. **Production Logging**: Uses `RUST_LOG=info` for production-appropriate logging
6. **Graceful Shutdown**: Handles SIGTERM/SIGINT with proper cleanup

## Production Deployment Guide

### Architecture Overview
In production, you run ONLY the components you control, while CoW Protocol runs their own infrastructure:

**Your Components:**
- `liquidity-driver` (port 8080): Fetches liquidity from all protocols
- `balancer-solver` (port 8083): Solves auctions using your liquidity

**CoW Protocol Components (they run these):**
- `autopilot`: Manages auction lifecycle
- `driver`: Processes auctions (WITHOUT liquidity sources)

### Production Flow
1. CoW's `autopilot` creates auctions
2. CoW's `driver` processes and validates orders (NO liquidity)
3. CoW's `driver` sends auction to YOUR `balancer-solver`:
   - **Mainnet**: `167.235.115.83:8100` ⭐ **LIVE**
   - **Arbitrum**: `167.235.115.83:8101` ⭐ **LIVE**
4. YOUR `balancer-solver` detects empty liquidity and calls YOUR `liquidity-driver`:
   - **Mainnet**: port 8080 (localhost)
   - **Arbitrum**: port 8081 (localhost)
5. YOUR `liquidity-driver` fetches all protocol liquidity and returns it
6. YOUR `balancer-solver` finds optimal routes and returns solution
7. CoW's `driver` executes the solution on-chain

### Production Checklist
- [ ] Configure RPC endpoints with production-grade providers
- [ ] Set up monitoring and alerting for both services
- [ ] Configure production logging (rotate logs, monitor disk usage)
- [ ] Set up reverse proxy/load balancer if needed
- [ ] Configure firewall rules (allow CoW to reach port 8083)
- [ ] Set up automated restarts/health checks
- [ ] Monitor liquidity-driver API latency and success rates
- [ ] Set up separate secrets management for production

## Customization

### RPC Endpoints
Update the `NODE_URL` variable in each setup script with your preferred RPC endpoint:

```bash
# Example for using Infura
NODE_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"

# Example for using Alchemy
NODE_URL="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY"
```

### Ports
You can change the ports by modifying these variables in the setup scripts:
```bash
DRIVER_PORT="11088"
SOLVER_PORT="8080"
```

### Multiple Solvers Port Allocation
**✅ RESOLVED**: Each chain now uses unique ports to avoid conflicts when running multiple production solvers:

| Chain     | Liquidity-Driver | Balancer-Solver | Production Status |
|-----------|------------------|-----------------|-------------------|
| Mainnet   | 8080             | **8100** ⭐     | **LIVE** `167.235.115.83:8100` |
| Arbitrum  | 8081             | **8101** ⭐     | **LIVE** `167.235.115.83:8101` |
| Gnosis    | 8082             | 8102            | Ready to deploy |
| Base      | 8083             | 8103            | Ready to deploy |
| Polygon   | 8084             | 8104            | Ready to deploy |
| Avalanche | 8085             | 8105            | Ready to deploy |

**CoW Protocol Integration**: Update the `endpoint` in CoW's solver configuration to point to your balancer-solver:
```toml
# For Mainnet (LIVE)
endpoint = "http://167.235.115.83:8100"

# For Arbitrum (LIVE)
endpoint = "http://167.235.115.83:8101"

# For future chains (when deployed)
endpoint = "http://167.235.115.83:8102"  # Gnosis
endpoint = "http://167.235.115.83:8103"  # Base
endpoint = "http://167.235.115.83:8104"  # Polygon
endpoint = "http://167.235.115.83:8105"  # Avalanche
```

### Orderbook URLs
Each script uses the staging orderbook for testing. For production, you would use:
- Mainnet: `https://api.cow.fi/mainnet/api`
- Gnosis: `https://api.cow.fi/xdai/api`
- Arbitrum: `https://api.cow.fi/arbitrum_one/api`
- Base: `https://api.cow.fi/base/api`
- Polygon: `https://api.cow.fi/polygon/api`
- Avalanche: `https://api.cow.fi/avalanche/api`

## Notes

- All configurations include Balancer V2 support
- Uniswap V2/V3 configurations are commented out but can be enabled
- Each chain uses the same CoW Protocol settlement contract address
- The Graph API key is shared across all chains
- Order priority strategies are optimized for production use
- Gas price caps and slippage settings are chain-appropriate

## Troubleshooting

1. **Ensure you're in the root directory** when running the scripts
2. **Check Rust installation**: `cargo --version`
3. **Verify services directory exists**: `ls services/`
4. **Check port availability**: Make sure ports 8080 and 11088 are free
5. **Update RPC endpoints**: Replace the default RPC URLs with your own 