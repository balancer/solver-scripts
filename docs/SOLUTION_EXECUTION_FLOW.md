# Solution Execution Flow - From Solve to On-Chain Settlement

## Overview

When your Balancer solver solution wins a CoW Protocol auction, it goes through a multi-step process from being selected as the winner to being executed on-chain. This document explains the complete flow.

## The Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CoW Protocol Autopilot                           │
│                     (Centralized Competition Manager)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    1. New auction created from user orders
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Autopilot: Fetch Solutions                          │
│                                                                           │
│  • Collects liquidity from on-chain                                     │
│  • Sends `/solve` requests to ALL registered solvers                    │
│  • Timeout: ~20 seconds                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌──────────────┐        ┌──────────────┐      ┌──────────────┐
    │   Driver 1   │        │   Driver 2   │  ... │   Driver N   │
    │ (e.g. 0x...  │        │ (e.g. Gnosis │      │ (Other       │
    │  Balancer)   │        │   Solver)    │      │  Solvers)    │
    └──────────────┘        └──────────────┘      └──────────────┘
            │                       │                       │
            │ 2. POST /solve        │                       │
            ▼                       ▼                       ▼
    ┌──────────────┐        ┌──────────────┐      ┌──────────────┐
    │ Balancer     │        │ Other        │      │ Other        │
    │ Solver       │        │ Solver       │      │ Solver       │
    │ (Your code!) │        │              │      │              │
    └──────────────┘        └──────────────┘      └──────────────┘
            │                       │                       │
            │ 3. Returns solution   │                       │
            └───────────────────────┴───────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Autopilot: Winner Selection                          │
│                                                                           │
│  • Scores all solutions                                                 │
│  • Ranks by: (User Surplus + Protocol Fees - Gas Cost)                 │
│  • Selects winner(s)                                                    │
│  • May select multiple winners if compatible                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┴────────────────────┐
            │                                            │
            ▼ (Winner)                                   ▼ (Loser)
    ┌──────────────┐                            ┌──────────────┐
    │ YOUR SOLUTION│                            │ Ignored      │
    │ IS WINNER!   │                            │              │
    └──────────────┘                            └──────────────┘
            │
            │ 4. POST /settle (to YOUR driver)
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Driver: Settle Endpoint                          │
│                                                                           │
│  • Receives: { solution_id, auction_id, deadline }                      │
│  • Retrieves solution from memory                                       │
│  • Encodes settlement transaction                                       │
└─────────────────────────────────────────────────────────────────────────┘
            │
            │ 5. Encode settlement
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Transaction Encoding Process                         │
│                                                                           │
│  A. Encode Trades (user orders)                                         │
│  B. Encode Clearing Prices                                              │
│  C. Encode Interactions (Balancer swaps!)                               │
│  D. Encode Pre/Post Interactions                                        │
│  E. Encode Approvals                                                    │
│  F. Add auction ID to calldata                                          │
└─────────────────────────────────────────────────────────────────────────┘
            │
            │ 6. Submit to blockchain
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Ethereum Blockchain                              │
│                                                                           │
│  Transaction calls:                                                      │
│  → GPv2Settlement.settle(...)                                           │
│     → Balancer Vault/Router (your interaction)                          │
│        → Pool executes swap                                             │
│     → Transfer tokens to user                                           │
│     → Transfer fees                                                     │
└─────────────────────────────────────────────────────────────────────────┘
            │
            │ 7. Confirmation
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Settlement Complete! 🎉                            │
│                                                                           │
│  • User receives tokens                                                 │
│  • Solver gets reward                                                   │
│  • Protocol collects fees                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailed Step-by-Step Flow

### Step 1: Autopilot Creates Auction

**Location**: `services/crates/autopilot/src/run_loop.rs`

The CoW Protocol autopilot:
1. Collects pending user orders from the order book
2. Fetches current on-chain liquidity (Balancer, Uniswap, Curve, etc.)
3. Packages this into an "auction"
4. Prepares to send to all registered solvers

**What's in the auction**:
```json
{
  "id": 11732945,
  "orders": [
    {
      "uid": "0x6f8c948b...",
      "sellToken": "0xc02aaa39...", // WETH
      "buyToken": "0xa0b86991...",  // USDC
      "sellAmount": "50000000000000000",
      "buyAmount": "150427599",      // User's minimum
      "kind": "sell",
      "partiallyFillable": false
    }
  ],
  "tokens": { /* token info */ },
  "effectiveGasPrice": "12000000000"
}
```

### Step 2: Solve Request Sent to YOUR Driver

**Endpoint**: `POST http://your-driver-host:8080/solve`

**Location**: `services/crates/driver/src/infra/api/routes/solve/mod.rs`

The autopilot sends the auction to **all registered solvers** simultaneously:

```rust
async fn route(
    state: axum::extract::State<State>,
    req: String,
) -> Result<axum::Json<dto::SolveResponse>, ...> {
    let competition = state.competition();
    let result = competition.solve(Arc::new(req)).await;
    // ...
}
```

**What YOUR driver receives**:
- Complete auction data (orders, tokens, liquidity)
- Deadline (usually ~20 seconds)
- Gas price estimates
- All available liquidity sources

### Step 3: Your Solver Processes the Request

**Location**: `services/crates/balancer-solver/src/api/routes/solve/mod.rs`

Your Balancer solver receives the request:

```rust
pub async fn solve(
    state: axum::extract::State<Arc<Solver>>,
    headers: axum::http::HeaderMap,
    axum::extract::Json(auction): axum::extract::Json<dto::Auction>,
) -> (axum::http::StatusCode, axum::response::Json<Response<dto::Solutions>>) {
    // Log the request
    tracing::info!(
        auction_id = ?auction.id,
        orders_count = auction.orders.len(),
        "🎯 RECEIVED SOLVE REQUEST FROM COW PROTOCOL"
    );
    
    // Solve the auction using Balancer pools
    let solutions = state.solve(auction).await;
    
    // Return the solution
    (StatusCode::OK, Json(Response::Ok(solutions)))
}
```

**Your solver**:
1. Analyzes available Balancer pools
2. Finds best routes for each order
3. Calculates expected output amounts
4. Estimates gas costs
5. Returns solution with:
   - Proposed trades
   - Interactions (Balancer pool calls)
   - Clearing prices
   - Gas estimate

**Example solution returned**:
```json
{
  "solutions": [{
    "id": 110,
    "trades": [{
      "order": "0x6f8c948b...",
      "executedAmount": "50000000000000000"
    }],
    "interactions": [{
      "kind": "liquidity",
      "internalize": true,
      "id": "161",
      "inputToken": "0xc02aaa39...",
      "outputToken": "0xa0b86991...",
      "inputAmount": "50000000000000000",
      "outputAmount": "157349944"
    }],
    "prices": {
      "0xc02aaa39...": "156109993",
      "0xa0b86991...": "49605989400351143"
    },
    "gas": 206391
  }]
}
```

### Step 4: Autopilot Selects Winner

**Location**: `services/crates/autopilot/src/run_loop.rs:318`

The autopilot collects ALL solutions from ALL solvers:

```rust
let solutions = self.fetch_solutions(&auction).await;
let ranking = self.winner_selection.arbitrate(solutions, &auction);
```

**Scoring formula**:
```
Score = User Surplus + Protocol Fees - Gas Cost (in ETH)
```

**Example**:
- Your solution: User gets 157.35 USDC (minimum was 150.43)
  - Surplus: 6.92 USDC (~$6.92)
  - Gas: 206,391 gas × 12 gwei = 0.00247 ETH (~$7.50)
  - **Score**: $6.92 + fees - $7.50 ≈ $X (depending on fees)

- Competitor solution: User gets 157.22 USDC
  - Surplus: 6.79 USDC
  - Gas: 250,000 gas = $9.00
  - **Score**: $6.79 + fees - $9.00 ≈ $Y

**Winner**: Highest score! 🏆

### Step 5: Settlement Request Sent Back to YOUR Driver

**Endpoint**: `POST http://your-driver-host:8080/settle`

**Location**: `services/crates/driver/src/infra/api/routes/settle/mod.rs`

Once you win, the autopilot calls your `/settle` endpoint:

```rust
async fn route(
    state: axum::extract::State<State>,
    req: axum::Json<dto::SettleRequest>,
) -> Result<(), ...> {
    state
        .competition()
        .settle(
            auction_id,
            req.solution_id,
            req.submission_deadline_latest_block,
        )
        .await
}
```

**Request body**:
```json
{
  "solution_id": 110,
  "auction_id": 11732945,
  "submission_deadline_latest_block": 21234567
}
```

**What happens next**:
1. Driver retrieves the solution from memory
2. Validates it's still executable
3. Begins encoding the settlement transaction

### Step 6: Encoding the Settlement Transaction

**Location**: `services/crates/driver/src/domain/competition/solution/encoding.rs:36`

This is where your Balancer swap gets turned into on-chain calldata!

```rust
pub fn tx(
    auction: &competition::Auction,
    solution: &super::Solution,
    contracts: &infra::blockchain::Contracts,
    approvals: impl Iterator<Item = eth::allowance::Approval>,
    internalization: settlement::Internalization,
    solver_native_token: ManageNativeToken,
) -> Result<eth::Tx, Error>
```

**The encoding process**:

#### 6A. Encode Tokens & Clearing Prices

```rust
let mut tokens = Vec::new();
let mut clearing_prices = Vec::new();

for (token, amount) in solution.clearing_prices() {
    tokens.push(token);
    clearing_prices.push(amount);
}
```

#### 6B. Encode Trades (User Orders)

```rust
for trade in solution.trades() {
    trades.push(Trade {
        sell_token_index: 0,
        buy_token_index: 1,
        receiver: trade.order.receiver,
        sell_amount: trade.executed_amount,
        buy_amount: trade.buy_amount,
        valid_to: trade.order.valid_to,
        // ... etc
    });
}
```

#### 6C. Encode YOUR Balancer Interaction! ⭐

This is the most important part - where your Balancer pool swap gets encoded!

**For Balancer V2 Pools**:
```rust
// Location: services/crates/solver/src/interactions/balancer_v2.rs
let single_swap = BalancerV2Vault::IVault::SingleSwap {
    poolId: self.pool_id,           // 0x9664693...0019
    kind: 1,                         // GivenOut
    assetIn: self.asset_in_max.token,   // WETH
    assetOut: self.asset_out.token,     // USDC
    amount: self.asset_out.amount,      // 157349944
    userData: self.user_data,           // empty bytes
};

let funds = BalancerV2Vault::IVault::FundManagement {
    sender: settlement_contract,
    fromInternalBalance: false,
    recipient: settlement_contract,
    toInternalBalance: false,
};

// Encodes to:
// vault.swap(single_swap, funds, max_amount_in, deadline)
```

**For Balancer V3 Pools**:
```rust
// Location: services/crates/solver/src/interactions/balancer_v3.rs
let method = batch_router.swap_exact_out(
    vec![(
        asset_in_token,        // WETH
        vec![(
            pool_address,      // 0x9664693...
            asset_out_token,   // USDC
            false,             // isBuffer
        )],
        max_amount_in,         // 50000000000000000
        exact_amount_out,      // 157349944
    )],
    deadline,                  // Far future
    false,                     // wethIsEth
    user_data,                 // empty
);
```

#### 6D. Encode Approvals (if needed)

```rust
for approval in approvals {
    interactions.push(encode_approval(approval));
}
```

#### 6E. Combine Everything into Settlement Call

```rust
let tx = contracts
    .settlement()
    .settle(
        tokens,                  // [WETH, USDC]
        clearing_prices,         // [156109993, 49605989400351143]
        trades,                  // [{ user order }]
        [
            pre_interactions,    // Before trading
            interactions,        // YOUR BALANCER SWAP! 🎯
            post_interactions,   // After trading (unwraps, etc.)
        ],
    )
    .into_inner();
```

#### 6F. Add Auction ID

```rust
let mut calldata = tx.data.unwrap().0;
calldata.extend(auction.id().to_be_bytes());
```

### Step 7: Submit Transaction to Blockchain

**Location**: `services/crates/driver/src/domain/mempools.rs`

The driver submits the transaction:

```rust
let tx_hash = self.eth
    .submit_transaction(tx, gas_price)
    .await?;
```

**The transaction**:
```
From: 0xYourSolverAddress
To: 0xGPv2Settlement (0x9008D19f58AAbD9eD0D60971565AA8510560ab41)
Data: settle(
  tokens=[WETH, USDC],
  clearingPrices=[...],
  trades=[...],
  interactions=[
    [],  // pre
    [    // intra (YOUR BALANCER SWAP!)
      {
        target: 0xBA12222222228d8Ba445958a75a0704d566BF2C8, // Balancer Vault
        calldata: swap(
          poolId=0x96646936b91d6b9d7d0c47c496afbf3d6ec7b6f8000200000000000000000019,
          assetIn=WETH,
          assetOut=USDC,
          amount=157349944,
          ...
        )
      }
    ],
    []   // post
  ]
)
```

### Step 8: On-Chain Execution

The settlement contract executes:

1. **Validate**: Check trade signatures, amounts, deadlines
2. **Transfer IN**: Pull user's sell tokens to settlement contract
   - User had approved settlement contract beforehand
   - `WETH.transferFrom(user, settlement, 50000000000000000)`
3. **Execute Pre-Interactions**: (none in this case)
4. **Execute YOUR BALANCER INTERACTION**: 🎯
   ```solidity
   // Settlement contract calls:
   BalancerVault.swap(
       poolId: 0x96646936...0019,
       assetIn: WETH (0xc02aaa39...),
       assetOut: USDC (0xa0b86991...),
       amount: 157349944,
       userData: 0x
   )
   
   // Inside Balancer Vault:
   // 1. Pull WETH from settlement contract
   // 2. Update pool balances
   // 3. Calculate swap output
   // 4. Send USDC back to settlement contract
   ```
5. **Execute Post-Interactions**: (unwraps if needed)
6. **Transfer OUT**: Send buy tokens to user
   - `USDC.transfer(user, 157349944)`
7. **Check Invariants**: Verify all orders filled correctly
8. **Emit Events**: Settlement event for tracking

**Success!** 🎉

### Step 9: Confirmation & Rewards

**What happens after**:
1. Transaction gets mined in a block
2. User receives their tokens
3. You (the solver) get a reward based on:
   - Surplus provided to user
   - Gas costs
   - Competition with other solvers
4. CoW Protocol collects protocol fees
5. Event is recorded in the database

## Key Files in Your Codebase

### Solver (Your Code)
```
services/crates/balancer-solver/
├── src/api/routes/solve/mod.rs       # Receives solve requests
├── src/domain/solver/mod.rs          # Main solving logic
└── src/domain/solver/balancer.rs     # Balancer-specific logic
```

### Driver (Execution)
```
services/crates/driver/
├── src/infra/api/routes/solve/mod.rs     # Solve endpoint
├── src/infra/api/routes/settle/mod.rs    # Settle endpoint  
├── src/domain/competition/mod.rs         # Competition logic
└── src/domain/competition/solution/
    ├── encoding.rs                       # Transaction encoding
    └── settlement.rs                     # Settlement creation
```

### Balancer Interactions
```
services/crates/solver/
├── src/interactions/balancer_v2.rs   # V2 swap encoding
└── src/interactions/balancer_v3.rs   # V3 swap encoding
```

## What Makes Your Solution Win?

Your solution wins based on **Objective Value**:

```rust
score = user_surplus + protocol_fees - gas_cost
```

**Maximizing your score**:
1. ✅ **Better prices** → More user surplus
2. ✅ **Lower gas** → Lower cost
3. ✅ **Reliable execution** → No reverts

**Why you might lose**:
1. ❌ Competitor found better liquidity source
2. ❌ Competitor used multi-hop routing
3. ❌ Competitor has lower gas (simpler route)
4. ❌ Your solution has higher price impact

## Current State of Your Solver

Based on your analysis:

### ✅ What Works
- **100% valid solutions** - All can execute on-chain
- **45.5% win rate** - Competitive with just Balancer
- **Clean execution** - Proper encoding, no issues
- **Gas efficient** - 206,391 gas per trade (single pool)

### 🎯 How to Improve

**1. Use V3 Pools** (Classification bug now fixed!)
```rust
// V3 pools have better capital efficiency
// Will automatically be used once classification is correct
```

**2. Multi-Pool Routing**
```rust
// Instead of: WETH → USDC (one pool)
// Do: WETH → DAI → USDC (two pools, better price)
```

**3. Stable Pools for Stablecoins**
```rust
// For USDC/DAI swaps, use Balancer Stable pools
// Much better pricing than weighted pools
```

**4. Order Splitting**
```rust
// For large orders, split across multiple pools
// Reduces price impact, increases win rate
```

## Testing the Flow

You can test this entire flow:

```bash
# 1. Start your solver
cd services
cargo run --bin balancer-solver

# 2. In another terminal, send a test solve request
curl -X POST http://localhost:8080/solve \
  -H "Content-Type: application/json" \
  -d @auction-data/mainnet/11732945_auction.json

# 3. Check the response for your solution

# 4. Test settlement (requires running driver)
curl -X POST http://localhost:8080/settle \
  -H "Content-Type: application/json" \
  -d '{"solution_id": 110, "auction_id": 11732945, "submission_deadline_latest_block": 21234567}'
```

## Debugging Tools

### View Logs
```bash
# Driver logs
grep "solving" logs/driver.log

# Settlement logs
grep "settling" logs/driver.log

# Balancer interaction logs
grep "balancer" logs/driver.log
```

### Check Settlement Transaction
```bash
# Get transaction hash from logs
# View on Etherscan:
https://etherscan.io/tx/0xYourTxHash

# Look for:
# - GPv2Settlement.settle() call
# - BalancerVault.swap() internal call
# - Token transfers
```

### Verify Solution
```bash
# Run verification script
python3 check_verification.py

# View specific auction
python3 view_analysis.py auction 11732945
```

## Summary

**The Flow in One Sentence**:
> CoW Autopilot sends auction → Your solver finds Balancer route → You return solution → Autopilot picks winner → Your driver encodes Balancer swap into settlement tx → Transaction executes on-chain → User gets tokens! 🎉

**Your Role**:
1. **Solving** (20 seconds): Find best Balancer route
2. **Encoding** (< 1 second): Turn route into transaction
3. **Execution** (automatic): Submit to blockchain

**Next Steps**:
1. ✅ V3 classification fixed
2. → Enable V3 pool usage
3. → Add multi-pool routing
4. → Optimize for different order sizes
5. → Beat more competitors! 🚀


