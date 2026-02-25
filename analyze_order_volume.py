#!/usr/bin/env python3
"""
Analyze order volume from auction data to understand request patterns.
Shows orders per auction over time, class breakdown (market vs limit),
fulfilled vs unfulfilled orders, and token pair frequency.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# Known Arbitrum token addresses
TOKEN_MAP = {
    "0x82af49447d8a07e3bd95bd0d56f14dc4146b60a5": "WETH",
    "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",
    "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": "USDC.e",
    "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT",
    "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": "DAI",
    "0x912ce59144191c1204e64559fe8253a0e49e6548": "ARB",
    "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f": "WBTC",
    "0xcb8b5cd20bdcaea9a010ac1f8d835824f5c87a04": "COW",
    "0x5979d7b546e38e414f7e9822514be443a4800529": "wstETH",
    "0xec70dcb4a1efa46b8f2d97c310c9c4790ba5ffa8": "rETH",
    "0x35751007a407ca6feffe80b3cb397736d2cf4dbe": "weETH",
    "0xba5ddd1f9d7f570dc94a51479a000e3bce967196": "AAVE",
    "0x17fc002b466eec40dae837fc4be5c67993ddbd6f": "FRAX",
    "0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a": "GMX",
    "0xf97f4df75117a78c1a5a0dbb814af92458539fb4": "LINK",
    "0xfa7f8980b0f1e64a2062791cc3b0871572f1f7f0": "UNI",
}


def token_name(address):
    """Convert token address to readable name."""
    return TOKEN_MAP.get(address.lower(), address[:10] + "..")


def analyze_order_volume():
    auction_dir = Path(os.environ.get("AUCTION_DIR", "/tmp/auction-data/arbitrum"))

    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return

    auction_files = sorted(auction_dir.glob("*_auction.json"))

    if not auction_files:
        print("No auction files found!")
        return

    print(f"Analyzing {len(auction_files)} auction files...\n")

    orders_per_auction = []
    token_pairs = defaultdict(int)
    hourly_auctions = defaultdict(lambda: {"auctions": 0, "total_orders": 0, "market": 0, "limit": 0})
    daily_auctions = defaultdict(lambda: {"auctions": 0, "total_orders": 0, "market": 0, "limit": 0})

    # Global counters
    total_market = 0
    total_limit = 0
    total_other_class = 0
    total_fulfilled = 0
    total_unfulfilled = 0

    for auction_file in auction_files:
        try:
            with open(auction_file) as f:
                data = json.load(f)

            orders = data.get("orders", [])
            order_count = len(orders)
            auction_id = auction_file.stem.replace("_auction", "")

            # Count order classes
            market_count = 0
            limit_count = 0
            for order in orders:
                order_class = order.get("class", "unknown").lower()
                if order_class == "market":
                    market_count += 1
                elif order_class == "limit":
                    limit_count += 1

            total_market += market_count
            total_limit += limit_count
            total_other_class += order_count - market_count - limit_count

            # Check corresponding solutions file for fulfilled orders
            solutions_file = auction_dir / f"{auction_id}_solutions.json"
            fulfilled_uids = set()
            if solutions_file.exists():
                try:
                    with open(solutions_file) as f:
                        sol_data = json.load(f)
                    for solution in sol_data.get("solutions", []):
                        for trade in solution.get("trades", []):
                            uid = trade.get("uid", trade.get("order", ""))
                            if uid:
                                fulfilled_uids.add(uid)
                except Exception:
                    pass

            fulfilled_count = len(fulfilled_uids)
            total_fulfilled += fulfilled_count
            total_unfulfilled += order_count - fulfilled_count

            # Get timestamp from file modification time
            mtime = auction_file.stat().st_mtime
            ts = datetime.fromtimestamp(mtime)
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            day_key = ts.strftime("%Y-%m-%d")

            orders_per_auction.append({
                "auction_id": auction_id,
                "order_count": order_count,
                "market": market_count,
                "limit": limit_count,
                "fulfilled": fulfilled_count,
                "timestamp": ts,
            })

            hourly_auctions[hour_key]["auctions"] += 1
            hourly_auctions[hour_key]["total_orders"] += order_count
            hourly_auctions[hour_key]["market"] += market_count
            hourly_auctions[hour_key]["limit"] += limit_count

            daily_auctions[day_key]["auctions"] += 1
            daily_auctions[day_key]["total_orders"] += order_count
            daily_auctions[day_key]["market"] += market_count
            daily_auctions[day_key]["limit"] += limit_count

            # Track token pairs
            for order in orders:
                sell_token = order.get("sell_token", order.get("sellToken", "?"))
                buy_token = order.get("buy_token", order.get("buyToken", "?"))
                pair = f"{token_name(sell_token)} → {token_name(buy_token)}"
                token_pairs[pair] += 1

        except Exception as e:
            print(f"  Error reading {auction_file.name}: {e}")

    if not orders_per_auction:
        print("No valid auction data found!")
        return

    # Summary stats
    order_counts = [a["order_count"] for a in orders_per_auction]
    total_orders = sum(order_counts)
    avg_orders = total_orders / len(order_counts)
    max_orders = max(order_counts)
    min_orders = min(order_counts)
    sorted_counts = sorted(order_counts)
    median_orders = sorted_counts[len(sorted_counts) // 2]

    market_counts = [a["market"] for a in orders_per_auction]
    limit_counts = [a["limit"] for a in orders_per_auction]
    fulfilled_counts = [a["fulfilled"] for a in orders_per_auction]

    first_ts = min(a["timestamp"] for a in orders_per_auction)
    last_ts = max(a["timestamp"] for a in orders_per_auction)
    duration_hours = (last_ts - first_ts).total_seconds() / 3600

    print("=" * 80)
    print("ORDER VOLUME SUMMARY")
    print("=" * 80)
    print(f"Time range:              {first_ts.strftime('%Y-%m-%d %H:%M')} -> {last_ts.strftime('%Y-%m-%d %H:%M')}")
    print(f"Duration:                {duration_hours:.1f} hours ({duration_hours/24:.1f} days)")
    print(f"Total auctions:          {len(orders_per_auction)}")
    print(f"Total orders:            {total_orders}")
    print(f"Avg orders/auction:      {avg_orders:.1f}")
    print(f"Median orders/auction:   {median_orders}")
    print(f"Min orders/auction:      {min_orders}")
    print(f"Max orders/auction:      {max_orders}")
    if duration_hours > 0:
        print(f"Avg auctions/hour:       {len(orders_per_auction) / duration_hours:.1f}")
        print(f"Avg orders/hour:         {total_orders / duration_hours:.1f}")

    # Order class breakdown
    print(f"\n{'=' * 80}")
    print("ORDER CLASS BREAKDOWN")
    print("=" * 80)
    market_pct = total_market / total_orders * 100 if total_orders > 0 else 0
    limit_pct = total_limit / total_orders * 100 if total_orders > 0 else 0
    print(f"  Market orders:         {total_market:>8} ({market_pct:>5.1f}%)  avg {sum(market_counts)/len(market_counts):.1f}/auction")
    print(f"  Limit orders:          {total_limit:>8} ({limit_pct:>5.1f}%)  avg {sum(limit_counts)/len(limit_counts):.1f}/auction")
    if total_other_class > 0:
        print(f"  Other/unknown:         {total_other_class:>8}")

    # Fulfilled breakdown
    print(f"\n{'=' * 80}")
    print("FULFILLED vs UNFULFILLED (by our solver)")
    print("=" * 80)
    fulfilled_pct = total_fulfilled / total_orders * 100 if total_orders > 0 else 0
    unfulfilled_pct = total_unfulfilled / total_orders * 100 if total_orders > 0 else 0
    avg_fulfilled = sum(fulfilled_counts) / len(fulfilled_counts) if fulfilled_counts else 0
    auctions_with_solutions = sum(1 for f in fulfilled_counts if f > 0)
    print(f"  Orders we solved:      {total_fulfilled:>8} ({fulfilled_pct:>5.1f}%)")
    print(f"  Orders unsolved:       {total_unfulfilled:>8} ({unfulfilled_pct:>5.1f}%)")
    print(f"  Avg solved/auction:    {avg_fulfilled:.2f}")
    print(f"  Auctions with solutions: {auctions_with_solutions}/{len(orders_per_auction)} ({auctions_with_solutions/len(orders_per_auction)*100:.1f}%)")

    # Distribution
    print(f"\n{'=' * 80}")
    print("ORDER COUNT DISTRIBUTION (total orders per auction)")
    print("=" * 80)
    buckets = defaultdict(int)
    for c in order_counts:
        if c == 0:
            buckets["0"] += 1
        elif c <= 5:
            buckets["1-5"] += 1
        elif c <= 10:
            buckets["6-10"] += 1
        elif c <= 25:
            buckets["11-25"] += 1
        elif c <= 50:
            buckets["26-50"] += 1
        elif c <= 100:
            buckets["51-100"] += 1
        elif c <= 500:
            buckets["101-500"] += 1
        elif c <= 1000:
            buckets["501-1000"] += 1
        else:
            buckets["1000+"] += 1

    for bucket in ["0", "1-5", "6-10", "11-25", "26-50", "51-100", "101-500", "501-1000", "1000+"]:
        count = buckets.get(bucket, 0)
        pct = count / len(order_counts) * 100
        bar = "#" * int(pct / 2)
        print(f"  {bucket:>8} orders: {count:>6} auctions ({pct:>5.1f}%) {bar}")

    # Daily breakdown
    print(f"\n{'=' * 80}")
    print("DAILY BREAKDOWN")
    print("=" * 80)
    print(f"  {'Date':<12} {'Auctions':>8} {'Orders':>8} {'Market':>8} {'Limit':>8} {'Limit%':>7}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*7}")
    for day in sorted(daily_auctions.keys()):
        d = daily_auctions[day]
        lpct = d["limit"] / d["total_orders"] * 100 if d["total_orders"] > 0 else 0
        print(f"  {day:<12} {d['auctions']:>8} {d['total_orders']:>8} {d['market']:>8} {d['limit']:>8} {lpct:>6.1f}%")

    # Hourly breakdown (last 24h)
    print(f"\n{'=' * 80}")
    print("HOURLY BREAKDOWN (last 24 hours)")
    print("=" * 80)
    print(f"  {'Hour':<18} {'Auctions':>8} {'Orders':>8} {'Market':>8} {'Limit':>8}")
    print(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    sorted_hours = sorted(hourly_auctions.keys())
    for hour in sorted_hours[-24:]:
        h = hourly_auctions[hour]
        print(f"  {hour:<18} {h['auctions']:>8} {h['total_orders']:>8} {h['market']:>8} {h['limit']:>8}")

    # Top token pairs
    print(f"\n{'=' * 80}")
    print("TOP 30 TOKEN PAIRS (by order frequency)")
    print("=" * 80)
    for pair, count in sorted(token_pairs.items(), key=lambda x: -x[1])[:30]:
        pct = count / total_orders * 100
        print(f"  {count:>6} ({pct:>5.1f}%) {pair}")

    # SOR query estimate
    print(f"\n{'=' * 80}")
    print("SOR QUERY ESTIMATE")
    print("=" * 80)
    print(f"If querying SOR for every order:")
    print(f"  Per auction (avg):     {avg_orders:.0f} queries")
    print(f"  Per auction (median):  {median_orders} queries")
    print(f"  Per auction (max):     {max_orders} queries")
    if duration_hours > 0:
        print(f"  Per hour (avg):        {total_orders / duration_hours:.0f} queries")
        print(f"  Per day (avg):         {total_orders / duration_hours * 24:.0f} queries")
    print(f"\nIf querying SOR for market orders only:")
    avg_market = total_market / len(orders_per_auction)
    print(f"  Per auction (avg):     {avg_market:.0f} queries")
    if duration_hours > 0:
        print(f"  Per hour (avg):        {total_market / duration_hours:.0f} queries")
        print(f"  Per day (avg):         {total_market / duration_hours * 24:.0f} queries")


if __name__ == "__main__":
    analyze_order_volume()
