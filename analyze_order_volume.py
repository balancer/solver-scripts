#!/usr/bin/env python3
"""
Analyze order volume from auction data to understand request patterns.
Shows orders per auction over time, class breakdown (market vs limit),
fulfilled vs unfulfilled orders, fillability by reference price, and token pair frequency.
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


def parse_uint256(value):
    """Parse a uint256 value that could be decimal string or hex."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.startswith("0x"):
            return int(value, 16)
        return int(value)
    return 0


def check_fillability(order, tokens):
    """
    Check if an order is potentially fillable at current market prices
    using reference prices from the auction's token metadata.

    Returns (is_fillable, deviation_pct) where deviation_pct is how far
    the order's limit price is from the market price.
    Positive deviation = order is generous (easy to fill).
    Negative deviation = order wants better than market (hard to fill).
    """
    sell_token = order.get("sellToken", order.get("sell_token", ""))
    buy_token = order.get("buyToken", order.get("buy_token", ""))
    sell_amount = parse_uint256(order.get("sellAmount", order.get("sell_amount", "0")))
    buy_amount = parse_uint256(order.get("buyAmount", order.get("buy_amount", "0")))
    kind = order.get("kind", "sell").lower()

    if sell_amount == 0 or buy_amount == 0:
        return False, None, "zero_amount"

    # Get reference prices (in ETH terms, as wei per unit)
    sell_token_data = tokens.get(sell_token, {})
    buy_token_data = tokens.get(buy_token, {})

    sell_ref = sell_token_data.get("referencePrice")
    buy_ref = buy_token_data.get("referencePrice")

    if sell_ref is None or buy_ref is None:
        return False, None, "no_ref_price"

    sell_ref = parse_uint256(sell_ref)
    buy_ref = parse_uint256(buy_ref)

    if sell_ref == 0 or buy_ref == 0:
        return False, None, "zero_ref_price"

    # Order's limit rate: how many buy tokens per sell token
    # For a sell order: user sells sell_amount and wants at least buy_amount
    # For a buy order: user buys buy_amount and is willing to sell at most sell_amount
    # In both cases: order_rate = buy_amount / sell_amount (buy per sell)
    order_rate = buy_amount / sell_amount

    # Market rate using reference prices:
    # referencePrice is in ETH per token unit (normalized)
    # market_rate = sell_ref / buy_ref = how many buy tokens per sell token at market
    market_rate = sell_ref / buy_ref

    if market_rate == 0:
        return False, None, "zero_market_rate"

    # Deviation: positive means order asks for LESS than market (easy to fill)
    # negative means order asks for MORE than market (hard to fill)
    deviation_pct = (market_rate - order_rate) / market_rate * 100

    # Order is fillable if market can deliver at least what the order asks
    # i.e., market_rate >= order_rate, i.e., deviation >= 0
    # We use a small tolerance of -1% to account for slippage/fees
    is_fillable = deviation_pct >= -1.0

    return is_fillable, deviation_pct, "ok"


def analyze_order_volume(hours=24):
    auction_dir = Path(os.environ.get("AUCTION_DIR", "/tmp/auction-data/arbitrum"))

    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return

    all_auction_files = sorted(auction_dir.glob("*_auction.json"))

    if not all_auction_files:
        print("No auction files found!")
        return

    # Filter to files from the last N hours
    cutoff = datetime.now().timestamp() - (hours * 3600)
    auction_files = [f for f in all_auction_files if f.stat().st_mtime >= cutoff]

    if not auction_files:
        print(f"No auction files found in the last {hours} hours!")
        print(f"(Total files available: {len(all_auction_files)})")
        return

    print(f"Analyzing {len(auction_files)} auction files from the last {hours} hours")
    print(f"(Skipped {len(all_auction_files) - len(auction_files)} older files)\n")

    orders_per_auction = []
    token_pairs = defaultdict(int)
    fillable_token_pairs = defaultdict(int)
    hourly_auctions = defaultdict(lambda: {"auctions": 0, "total_orders": 0, "market": 0, "limit": 0})
    daily_auctions = defaultdict(lambda: {
        "auctions": 0, "total_orders": 0, "market": 0, "limit": 0,
        "fillable": 0, "unfillable": 0, "no_ref": 0,
    })

    # Global counters
    total_market = 0
    total_limit = 0
    total_other_class = 0
    total_fulfilled = 0
    total_unfulfilled = 0

    # Fillability counters
    total_fillable = 0
    total_unfillable = 0
    total_no_ref = 0
    all_deviations = []
    fillable_deviations = []

    # Per-auction fillable counts for distribution
    fillable_per_auction = []

    # Competition data counters
    total_competition_filled = 0
    total_competition_auctions = 0
    competition_filled_per_auction = []
    competition_solvers = defaultdict(lambda: {"wins": 0, "orders_filled": 0})
    auctions_with_no_winner = 0

    for auction_file in auction_files:
        try:
            with open(auction_file) as f:
                data = json.load(f)

            orders = data.get("orders", [])
            tokens = data.get("tokens", {})
            order_count = len(orders)
            auction_id = auction_file.stem.replace("_auction", "")

            # Count order classes and fillability
            market_count = 0
            limit_count = 0
            auction_fillable = 0
            auction_unfillable = 0
            auction_no_ref = 0

            for order in orders:
                order_class = order.get("class", "unknown").lower()
                if order_class == "market":
                    market_count += 1
                elif order_class == "limit":
                    limit_count += 1

                # Check fillability
                is_fillable, deviation, reason = check_fillability(order, tokens)
                if reason != "ok":
                    auction_no_ref += 1
                    total_no_ref += 1
                elif is_fillable:
                    auction_fillable += 1
                    total_fillable += 1
                    fillable_deviations.append(deviation)
                    # Track fillable token pairs
                    sell_token = order.get("sellToken", order.get("sell_token", "?"))
                    buy_token = order.get("buyToken", order.get("buy_token", "?"))
                    pair = f"{token_name(sell_token)} -> {token_name(buy_token)}"
                    fillable_token_pairs[pair] += 1
                else:
                    auction_unfillable += 1
                    total_unfillable += 1

                if deviation is not None:
                    all_deviations.append(deviation)

            total_market += market_count
            total_limit += limit_count
            total_other_class += order_count - market_count - limit_count
            fillable_per_auction.append(auction_fillable)

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

            # Check competition data for orders actually filled by ANY solver
            competition_file = auction_dir / f"{auction_id}_competition.json"
            auction_competition_filled = 0
            if competition_file.exists():
                try:
                    with open(competition_file) as f:
                        comp_data = json.load(f)
                    total_competition_auctions += 1
                    solutions = comp_data.get("solutions", [])
                    winner = None
                    for sol in solutions:
                        if sol.get("isWinner"):
                            winner = sol
                            break
                    if winner:
                        winner_orders = winner.get("orders", [])
                        auction_competition_filled = len(winner_orders)
                        total_competition_filled += auction_competition_filled
                        solver_addr = winner.get("solverAddress", "unknown")
                        competition_solvers[solver_addr]["wins"] += 1
                        competition_solvers[solver_addr]["orders_filled"] += len(winner_orders)
                    else:
                        auctions_with_no_winner += 1
                except Exception:
                    pass
            competition_filled_per_auction.append(auction_competition_filled)

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
                "fillable": auction_fillable,
                "competition_filled": auction_competition_filled,
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
            daily_auctions[day_key]["fillable"] += auction_fillable
            daily_auctions[day_key]["unfillable"] += auction_unfillable
            daily_auctions[day_key]["no_ref"] += auction_no_ref

            # Track token pairs
            for order in orders:
                sell_token = order.get("sellToken", order.get("sell_token", "?"))
                buy_token = order.get("buyToken", order.get("buy_token", "?"))
                pair = f"{token_name(sell_token)} -> {token_name(buy_token)}"
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

    # Fillability analysis
    total_checked = total_fillable + total_unfillable
    print(f"\n{'=' * 80}")
    print("FILLABILITY ANALYSIS (based on reference prices, -1% tolerance)")
    print("=" * 80)
    if total_checked > 0:
        fillable_pct = total_fillable / total_checked * 100
        unfillable_pct = total_unfillable / total_checked * 100
    else:
        fillable_pct = unfillable_pct = 0
    print(f"  Potentially fillable:  {total_fillable:>8} ({fillable_pct:>5.1f}% of checked)")
    print(f"  Unfillable at market:  {total_unfillable:>8} ({unfillable_pct:>5.1f}% of checked)")
    print(f"  No reference price:    {total_no_ref:>8} (skipped)")
    print(f"  Total checked:         {total_checked:>8}")
    avg_fillable = sum(fillable_per_auction) / len(fillable_per_auction) if fillable_per_auction else 0
    max_fillable = max(fillable_per_auction) if fillable_per_auction else 0
    sorted_fillable = sorted(fillable_per_auction)
    median_fillable = sorted_fillable[len(sorted_fillable) // 2] if sorted_fillable else 0
    print(f"\n  Avg fillable/auction:  {avg_fillable:.1f}")
    print(f"  Median fillable/auc:   {median_fillable}")
    print(f"  Max fillable/auction:  {max_fillable}")

    # Deviation distribution
    if all_deviations:
        sorted_devs = sorted(all_deviations)
        print(f"\n  Price deviation distribution (market_rate vs order_rate):")
        print(f"  (positive = order asks less than market, easy to fill)")
        print(f"  (negative = order asks more than market, hard to fill)")
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        for p in percentiles:
            idx = int(len(sorted_devs) * p / 100)
            idx = min(idx, len(sorted_devs) - 1)
            print(f"    p{p:<3}: {sorted_devs[idx]:>8.1f}%")

    # Fillable orders distribution per auction
    print(f"\n{'=' * 80}")
    print("FILLABLE ORDERS PER AUCTION DISTRIBUTION")
    print("=" * 80)
    fill_buckets = defaultdict(int)
    for c in fillable_per_auction:
        if c == 0:
            fill_buckets["0"] += 1
        elif c <= 2:
            fill_buckets["1-2"] += 1
        elif c <= 5:
            fill_buckets["3-5"] += 1
        elif c <= 10:
            fill_buckets["6-10"] += 1
        elif c <= 20:
            fill_buckets["11-20"] += 1
        elif c <= 50:
            fill_buckets["21-50"] += 1
        else:
            fill_buckets["50+"] += 1

    for bucket in ["0", "1-2", "3-5", "6-10", "11-20", "21-50", "50+"]:
        count = fill_buckets.get(bucket, 0)
        pct = count / len(fillable_per_auction) * 100 if fillable_per_auction else 0
        bar = "#" * int(pct / 2)
        print(f"  {bucket:>5} fillable: {count:>6} auctions ({pct:>5.1f}%) {bar}")

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

    # Competition data: orders actually filled by ANY solver (winner)
    print(f"\n{'=' * 80}")
    print("ORDERS ACTUALLY FILLED (by competition winner)")
    print("=" * 80)
    if total_competition_auctions > 0:
        avg_comp_filled = total_competition_filled / total_competition_auctions
        comp_filled_nonzero = [c for c in competition_filled_per_auction if c > 0]
        max_comp_filled = max(competition_filled_per_auction) if competition_filled_per_auction else 0
        sorted_comp = sorted(competition_filled_per_auction)
        median_comp = sorted_comp[len(sorted_comp) // 2]
        auctions_with_winner = total_competition_auctions - auctions_with_no_winner

        print(f"  Auctions with competition data: {total_competition_auctions}")
        print(f"  Auctions with a winner:    {auctions_with_winner} ({auctions_with_winner/total_competition_auctions*100:.1f}%)")
        print(f"  Auctions with no winner:   {auctions_with_no_winner}")
        print(f"  Total orders filled:       {total_competition_filled}")
        print(f"  Avg filled/auction:        {avg_comp_filled:.2f}")
        print(f"  Median filled/auction:     {median_comp}")
        print(f"  Max filled/auction:        {max_comp_filled}")

        # Compare with our solver
        print(f"\n  Comparison:")
        print(f"    Our solver proposed:     {total_fulfilled} solutions across all auctions")
        print(f"    Competition filled:      {total_competition_filled} orders across {total_competition_auctions} auctions")

        # Distribution of filled orders per auction
        comp_buckets = defaultdict(int)
        for c in competition_filled_per_auction:
            if c == 0:
                comp_buckets["0"] += 1
            elif c == 1:
                comp_buckets["1"] += 1
            elif c <= 3:
                comp_buckets["2-3"] += 1
            elif c <= 5:
                comp_buckets["4-5"] += 1
            elif c <= 10:
                comp_buckets["6-10"] += 1
            else:
                comp_buckets["10+"] += 1

        print(f"\n  Filled orders per auction distribution:")
        for bucket in ["0", "1", "2-3", "4-5", "6-10", "10+"]:
            count = comp_buckets.get(bucket, 0)
            pct = count / len(competition_filled_per_auction) * 100 if competition_filled_per_auction else 0
            bar = "#" * int(pct / 2)
            print(f"    {bucket:>5} filled: {count:>6} auctions ({pct:>5.1f}%) {bar}")

        # Top winning solvers
        print(f"\n  Top winning solvers:")
        for addr, stats in sorted(competition_solvers.items(), key=lambda x: -x[1]["wins"])[:10]:
            print(f"    {addr[:10]}..{addr[-6:]}: {stats['wins']:>5} wins, {stats['orders_filled']:>6} orders filled")
    else:
        print("  No competition data available")

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

    # Daily breakdown with fillability
    print(f"\n{'=' * 80}")
    print("DAILY BREAKDOWN")
    print("=" * 80)
    print(f"  {'Date':<12} {'Auctions':>8} {'Orders':>8} {'Fillable':>8} {'Fill%':>6} {'Avg Fill/Auc':>12}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*12}")
    for day in sorted(daily_auctions.keys()):
        d = daily_auctions[day]
        checked = d["fillable"] + d["unfillable"]
        fpct = d["fillable"] / checked * 100 if checked > 0 else 0
        avg_f = d["fillable"] / d["auctions"] if d["auctions"] > 0 else 0
        print(f"  {day:<12} {d['auctions']:>8} {d['total_orders']:>8} {d['fillable']:>8} {fpct:>5.1f}% {avg_f:>12.1f}")

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

    # Top token pairs (all)
    print(f"\n{'=' * 80}")
    print("TOP 30 TOKEN PAIRS (by order frequency)")
    print("=" * 80)
    for pair, count in sorted(token_pairs.items(), key=lambda x: -x[1])[:30]:
        pct = count / total_orders * 100
        print(f"  {count:>6} ({pct:>5.1f}%) {pair}")

    # Top FILLABLE token pairs
    print(f"\n{'=' * 80}")
    print("TOP 20 FILLABLE TOKEN PAIRS (orders near market price)")
    print("=" * 80)
    if fillable_token_pairs:
        for pair, count in sorted(fillable_token_pairs.items(), key=lambda x: -x[1])[:20]:
            pct = count / total_fillable * 100 if total_fillable > 0 else 0
            print(f"  {count:>6} ({pct:>5.1f}%) {pair}")
    else:
        print("  No fillable orders found")

    # SOR query estimate
    print(f"\n{'=' * 80}")
    print("SOR QUERY ESTIMATE")
    print("=" * 80)
    print(f"If querying SOR for every order:")
    print(f"  Per auction (avg):     {avg_orders:.0f} queries")
    print(f"  Per auction (max):     {max_orders} queries")
    if duration_hours > 0:
        print(f"  Per day (avg):         {total_orders / duration_hours * 24:.0f} queries")
    print(f"\nIf querying SOR for fillable orders only (reference price filter):")
    print(f"  Per auction (avg):     {avg_fillable:.1f} queries")
    print(f"  Per auction (median):  {median_fillable} queries")
    print(f"  Per auction (max):     {max_fillable} queries")
    if duration_hours > 0:
        print(f"  Per hour (avg):        {total_fillable / duration_hours:.0f} queries")
        print(f"  Per day (avg):         {total_fillable / duration_hours * 24:.0f} queries")
    print(f"\n  --> Filtering reduces queries by ~{(1 - total_fillable/max(total_checked,1))*100:.1f}%")


if __name__ == "__main__":
    import sys
    hours = 24
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python3 analyze_order_volume.py [hours]")
            print(f"  Default: 24 hours. Use 0 for all data.")
            sys.exit(1)
    if hours == 0:
        hours = 999999  # effectively all data
    analyze_order_volume(hours)
