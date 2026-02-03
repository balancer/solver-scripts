# Balancer Solver Workflow: Complete Process Analysis

## Overview

This document provides a comprehensive, step-by-step analysis of the Balancer solver's workflow from receiving auction data from CoW Protocol to returning optimal trading solutions.

## 1. Auction Reception and Initial Processing

### 1.1 HTTP Request Handling
- **Endpoint**: `POST /solve`
- **Source**: CoW Protocol driver
- **Content-Type**: `application/json`
- **Authentication**: Request headers logged for debugging

```rust
// From: services/crates/balancer-solver/src/api/routes/solve/mod.rs
pub async fn solve(
    state: axum::extract::State<Arc<Solver>>,
    headers: axum::http::HeaderMap,
    axum::extract::Json(auction): axum::extract::Json<dto::Auction>,
) -> (axum::http::StatusCode, axum::response::Json<Response<dto::Solutions>>) {
```

### 1.2 Request Logging and Validation
The solver performs comprehensive logging for observability:

```rust
tracing::info!(
    auction_id = ?auction.id,
    orders_count = auction.orders.len(),
    "🎯 RECEIVED SOLVE REQUEST FROM COW PROTOCOL"
);

tracing::info!(
    order_index = i,
    sell_token = ?order.sell_token,
    buy_token = ?order.buy_token,
    sell_amount = ?order.sell_amount,
    buy_amount = ?order.buy_amount,
    kind = ?order.kind,
    "📝 ORDER DETAILS"
);
```

### 1.3 Configuration Extraction
The solver extracts runtime configuration from its state:

```rust
let base_tokens = {
    let tokens: Vec<_> = state.base_tokens().iter().map(|t| t.0).collect();
    if tokens.is_empty() { None } else { Some(tokens) }
};
let protocols = state.protocols();
```

## 2. Auction Data Transformation

### 2.1 Domain Object Conversion
The raw auction DTO is converted to internal domain objects:

```rust
// From: services/crates/balancer-solver/src/api/routes/solve/dto/auction.rs
pub async fn into_domain(
    auction: Auction,
    liquidity_client: Option<&LiquidityClient>,
    base_tokens: Option<&[eth::H160]>,
    protocols: Option<&[String]>,
) -> Result<auction::Auction, Error> {
```

### 2.2 Token Processing
Each token in the auction is converted with complete metadata:

```rust
auction::Tokens(
    auction.tokens.iter().map(|(address, token)| {
        (
            eth::TokenAddress(*address),
            auction::Token {
                decimals: token.decimals,
                symbol: token.symbol.clone(),
                reference_price: token.reference_price.map(eth::Ether).map(auction::Price),
                available_balance: token.available_balance,
                trusted: token.trusted,
            },
        )
    }).collect(),
)
```

### 2.3 Order Processing
Orders are converted with all execution parameters:

```rust
order::Order {
    uid: order::Uid(order.uid),
    sell: eth::Asset {
        token: eth::TokenAddress(order.sell_token),
        amount: order.sell_amount,
    },
    buy: eth::Asset {
        token: eth::TokenAddress(order.buy_token),
        amount: order.buy_amount,
    },
    side: match order.kind {
        Kind::Buy => order::Side::Buy,
        Kind::Sell => order::Side::Sell,
    },
    class: match order.class {
        Class::Market => order::Class::Market,
        Class::Limit => order::Class::Limit,
    },
    partially_fillable: order.partially_fillable,
    // ... additional fields
}
```

## 3. Liquidity Management Strategy

### 3.1 Mode Detection
The solver detects which liquidity mode to use:

```rust
liquidity: {
    if auction.liquidity.is_empty() && liquidity_client.is_some() {
        // 3.2 Mode A: Independent Liquidity Fetching
    } else {
        // 3.3 Mode B: Embedded Liquidity
    }
}
```

### 3.2 Mode A: Independent Liquidity Fetching

#### 3.2.1 Token Pair Extraction
Extracts direct pairs from auction orders:

```rust
fn extract_token_pairs_from_auction(
    auction: &Auction,
    base_tokens: Option<&[eth::H160]>,
) -> Vec<(eth::H160, eth::H160)> {
    let mut result = HashSet::new();

    // Extract direct pairs from orders
    for order in &auction.orders {
        if order.sell_token != order.buy_token {
            let pair = if order.sell_token < order.buy_token {
                (order.sell_token, order.buy_token)
            } else {
                (order.buy_token, order.sell_token)
            };
            result.insert(pair);
        }
    }
    // ... base token expansion logic
}
```

#### 3.2.2 Smart Token Pair Expansion
Expands direct pairs using base tokens for comprehensive routing:

```rust
// Example expansion for AAVE/USDC order:
// Original: [AAVE ↔ USDC]
// Expanded: [
//   AAVE ↔ USDC,     // Direct pair
//   AAVE ↔ WETH,     // Base token routing
//   AAVE ↔ DAI,      // Alternative routes
//   USDC ↔ WETH,     // Base routing
//   USDC ↔ DAI,      // Cross-base routing
//   WETH ↔ DAI       // Base-base pairs
// ]
```

#### 3.2.3 Liquidity Driver API Request
Makes HTTP request to external liquidity driver:

```rust
let request = LiquidityRequest {
    auction_id: auction.id.unwrap_or(0) as u64,
    tokens: auction.tokens.keys().copied().collect(),
    token_pairs,
    block_number: estimated_block_number,
    protocols: protocols.map(|p| p.to_vec()).unwrap_or_else(|| {
        vec!["balancer_v2".to_string(), "uniswap_v2".to_string()]
    }),
};

match client.fetch_liquidity(request).await {
    Ok(response) => {
        // Convert DTO liquidity to domain objects
        response.liquidity.iter()
            .map(|liquidity| convert_dto_liquidity_to_domain(liquidity))
            .try_collect()?
    }
    Err(e) => {
        tracing::warn!("Failed to fetch liquidity - continuing with empty");
        Vec::new() // Graceful degradation
    }
}
```

### 3.3 Mode B: Embedded Liquidity
Uses liquidity data embedded in the auction:

```rust
auction.liquidity.iter()
    .map(|liquidity| convert_dto_liquidity_to_domain(liquidity))
    .try_collect()?
```

## 4. Route Finding Algorithm

### 4.1 Baseline Solver Initialization
Creates boundary solver with all liquidity sources:

```rust
let boundary_solver = boundary::baseline::Solver::new(
    &self.weth,
    &self.base_tokens,
    &auction.liquidity,
    self.uni_v3_quoter_v2.clone(),
    self.erc4626_web3.as_ref(),
);
```

### 4.2 Path Candidate Generation
Uses `BaseTokens` strategy for comprehensive path discovery:

```rust
// From: services/crates/shared/src/baseline_solver.rs
pub fn path_candidates_with_hops(
    &self,
    sell_token: H160,
    buy_token: H160,
    max_hops: usize,
) -> HashSet<PathCandidate> {
    path_candidates(sell_token, buy_token, &self.tokens, max_hops)
}
```

#### 4.2.1 Path Generation Algorithm
For `sell_token` → `buy_token` with base tokens `[WETH, USDC, DAI]`:

- **0 hops**: `[sell_token, buy_token]`
- **1 hop**: `[sell_token, WETH, buy_token]`, `[sell_token, USDC, buy_token]`, `[sell_token, DAI, buy_token]`
- **2 hops**: All combinations of base tokens as intermediates

### 4.3 Route Estimation
For each path candidate, estimates optimal amounts:

```rust
// For buy orders: estimate_sell_amount(buy_amount, path, liquidity)
// For sell orders: estimate_buy_amount(sell_amount, path, liquidity)
```

#### 4.3.1 Multi-Pool Testing
For each hop in the path, tests all available pools:

```rust
let outputs = futures::future::join_all(pools.iter().map(|liquidity| async move {
    let output = liquidity.get_amount_out(*current, (amount, previous_token)).await;
    output.map(|output| (liquidity, output))
})).await;

let (best_liquidity, amount) = outputs
    .into_iter()
    .flatten()
    .max_by_key(|(_, amount)| *amount)?;
```

### 4.4 Multi-Hop Execution
Traverses the selected path, accumulating results:

```rust
async fn traverse_path(
    &self,
    path: &[&OnchainLiquidity],
    mut sell_token: H160,
    mut sell_amount: U256,
) -> Option<Vec<solver::Segment>> {
    let mut segments = Vec::new();
    for liquidity in path {
        let buy_token = liquidity.token_pair.other(&sell_token).unwrap();
        let buy_amount = liquidity.get_amount_out(buy_token, (sell_amount, sell_token)).await?;

        segments.push(solver::Segment {
            liquidity: reference_liquidity,
            input: eth::Asset { token: eth::TokenAddress(sell_token), amount: sell_amount },
            output: eth::Asset { token: eth::TokenAddress(buy_token), amount: buy_amount },
            gas: eth::Gas(liquidity.gas_cost().await.into()),
        });

        sell_token = buy_token;
        sell_amount = buy_amount;
    }
    Some(segments)
}
```

## 5. Solution Generation and Response

### 5.1 Partial Fill Optimization
For partially fillable orders, tests multiple execution amounts:

```rust
fn requests_for_order(&self, order: &Order) -> impl Iterator<Item = Request> + use<> {
    let n = if order.partially_fillable {
        self.max_partial_attempts
    } else {
        1
    };

    (0..n).map(move |i| {
        let divisor = U256::one() << i;
        Request {
            sell: eth::Asset {
                token: sell.token,
                amount: sell.amount / divisor,
            },
            buy: eth::Asset {
                token: buy.token,
                amount: buy.amount / divisor,
            },
            side,
        }
    })
}
```

### 5.2 Solution Construction
Creates complete solution with all execution data:

```rust
let mut output = route.output();
if let order::Side::Buy = order.side {
    output.amount = cmp::min(output.amount, order.buy.amount); // Cap buy orders
}

let gas = route.gas() + self.solution_gas_offset;
let fee = sell_token_price.ether_value(eth::Ether(gas.0.checked_mul(auction.gas_price.0.0)?))?.into();

Some(
    solution::Single {
        order: order.clone(),
        input: route.input(),
        output,
        interactions,
        gas,
    }
    .into_solution(fee)?
    .with_id(solution::Id(i as u64))
    .with_buffers_internalizations(&auction.tokens),
)
```

### 5.3 Response Formatting
Converts solutions to CoW Protocol DTO format:

```rust
let solutions_dto = dto::solution::from_domain(&solutions);

(
    axum::http::StatusCode::OK,
    axum::response::Json(Response::Ok(solutions_dto)),
)
```

## Key Algorithm Characteristics

### Performance Optimizations
- **Async Processing**: CPU-intensive work runs in background thread
- **Timeout Protection**: Prevents long-running solves from blocking auctions
- **Concurrent Estimation**: Tests all path candidates in parallel
- **Smart Caching**: Block-aware caching for liquidity data

### Error Handling Strategy
- **Graceful Degradation**: Returns empty solutions rather than failing auctions
- **Failure Isolation**: Protocol failures don't block entire solving process
- **Comprehensive Logging**: Full observability for debugging and monitoring

### Route Quality Assurance
- **Multi-Protocol Support**: Handles all major DEX protocols
- **Price Impact Consideration**: Selects paths with optimal price/slippage trade-offs
- **Gas Efficiency**: Includes gas costs in path selection
- **Output Validation**: Ensures solutions meet order requirements

This workflow provides a robust, production-tested solution for finding optimal trading routes across multiple DEX protocols while maintaining compatibility with CoW Protocol's solver interface.

