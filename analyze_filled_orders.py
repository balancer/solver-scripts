#!/usr/bin/env python3
"""
Analyze characteristics of orders that actually get filled vs those that don't.
Cross-references auction data with competition results to understand what
distinguishes filled orders from stale limit orders.
"""

import json
import os
import sys
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
    return TOKEN_MAP.get(address.lower(), address[:10] + "..")


def parse_uint256(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.startswith("0x"):
            return int(value, 16)
        return int(value)
    return 0


def get_order_characteristics(order, tokens, auction_ts):
    """Extract key characteristics of an order."""
    sell_token = order.get("sellToken", order.get("sell_token", ""))
    buy_token = order.get("buyToken", order.get("buy_token", ""))
    sell_amount = parse_uint256(order.get("sellAmount", order.get("sell_amount", "0")))
    buy_amount = parse_uint256(order.get("buyAmount", order.get("buy_amount", "0")))
    valid_to = order.get("validTo", order.get("valid_to", 0))
    kind = order.get("kind", "sell").lower()
    partially_fillable = order.get("partiallyFillable", order.get("partially_fillable", False))
    uid = order.get("uid", "")

    # Time to expiry
    time_to_expiry = valid_to - int(auction_ts) if valid_to > 0 else None

    # Price deviation from reference
    sell_token_data = tokens.get(sell_token, {})
    buy_token_data = tokens.get(buy_token, {})
    sell_ref = parse_uint256(sell_token_data.get("referencePrice", "0"))
    buy_ref = parse_uint256(buy_token_data.get("referencePrice", "0"))

    deviation = None
    sell_value_eth = None
    if sell_ref > 0 and buy_ref > 0 and sell_amount > 0 and buy_amount > 0:
        order_rate = buy_amount / sell_amount
        market_rate = sell_ref / buy_ref
        if market_rate > 0:
            deviation = (market_rate - order_rate) / market_rate * 100

    # Estimate order size in ETH using reference price
    if sell_ref > 0 and sell_amount > 0:
        # referencePrice is price per token in ETH (as a fraction of 1e18)
        sell_value_eth = (sell_amount * sell_ref) / (10**36)

    return {
        "uid": uid,
        "sell_token": sell_token,
        "buy_token": buy_token,
        "sell_token_name": token_name(sell_token),
        "buy_token_name": token_name(buy_token),
        "pair": f"{token_name(sell_token)} -> {token_name(buy_token)}",
        "sell_amount": sell_amount,
        "buy_amount": buy_amount,
        "kind": kind,
        "partially_fillable": partially_fillable,
        "valid_to": valid_to,
        "time_to_expiry_seconds": time_to_expiry,
        "price_deviation_pct": deviation,
        "sell_value_eth": sell_value_eth,
    }


def categorize_expiry(seconds):
    """Categorize time to expiry into buckets."""
    if seconds is None:
        return "unknown"
    if seconds <= 0:
        return "expired"
    if seconds <= 120:  # 2 min
        return "< 2 min"
    if seconds <= 600:  # 10 min
        return "2-10 min"
    if seconds <= 3600:  # 1 hour
        return "10-60 min"
    if seconds <= 86400:  # 1 day
        return "1-24 hours"
    if seconds <= 604800:  # 1 week
        return "1-7 days"
    return "> 7 days"


EXPIRY_ORDER = ["expired", "< 2 min", "2-10 min", "10-60 min", "1-24 hours", "1-7 days", "> 7 days", "unknown"]


def analyze_filled_orders(hours=24):
    auction_dir = Path(os.environ.get("AUCTION_DIR", "/tmp/auction-data/arbitrum"))

    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return

    all_auction_files = sorted(auction_dir.glob("*_auction.json"))
    if not all_auction_files:
        print("No auction files found!")
        return

    cutoff = datetime.now().timestamp() - (hours * 3600)
    auction_files = [f for f in all_auction_files if f.stat().st_mtime >= cutoff]

    if not auction_files:
        print(f"No auction files found in the last {hours} hours!")
        return

    print(f"Analyzing filled vs unfilled orders from {len(auction_files)} auctions (last {hours}h)\n")

    filled_orders = []
    unfilled_orders = []
    auctions_processed = 0
    auctions_with_competition = 0
    auctions_with_winner = 0

    for auction_file in auction_files:
        try:
            with open(auction_file) as f:
                auction_data = json.load(f)

            orders = auction_data.get("orders", [])
            tokens = auction_data.get("tokens", {})
            auction_id = auction_file.stem.replace("_auction", "")
            auction_ts = auction_file.stat().st_mtime
            auctions_processed += 1

            # Build order lookup by UID
            order_by_uid = {}
            for order in orders:
                uid = order.get("uid", "")
                if uid:
                    order_by_uid[uid] = order

            # Read competition data
            competition_file = auction_dir / f"{auction_id}_competition.json"
            if not competition_file.exists():
                continue

            with open(competition_file) as f:
                comp_data = json.load(f)

            auctions_with_competition += 1

            # Find winner and their filled order IDs
            winner = None
            for sol in comp_data.get("solutions", []):
                if sol.get("isWinner"):
                    winner = sol
                    break

            if not winner:
                continue

            auctions_with_winner += 1
            filled_uids = set()
            for winner_order in winner.get("orders", []):
                filled_uids.add(winner_order.get("id", ""))

            # Classify each order
            for order in orders:
                uid = order.get("uid", "")
                chars = get_order_characteristics(order, tokens, auction_ts)
                chars["auction_id"] = auction_id

                if uid in filled_uids:
                    filled_orders.append(chars)
                else:
                    unfilled_orders.append(chars)

        except Exception as e:
            print(f"  Error processing {auction_file.name}: {e}")

    if not filled_orders:
        print("No filled orders found in the data!")
        print(f"  Auctions processed: {auctions_processed}")
        print(f"  With competition data: {auctions_with_competition}")
        print(f"  With a winner: {auctions_with_winner}")
        return

    print("=" * 90)
    print("FILLED vs UNFILLED ORDER ANALYSIS")
    print("=" * 90)
    print(f"  Auctions analyzed:         {auctions_processed}")
    print(f"  With competition data:     {auctions_with_competition}")
    print(f"  With a winner:             {auctions_with_winner}")
    print(f"  Total filled orders:       {len(filled_orders)}")
    print(f"  Total unfilled orders:     {len(unfilled_orders)}")

    # === TIME TO EXPIRY ===
    print(f"\n{'=' * 90}")
    print("TIME TO EXPIRY (at auction time)")
    print("=" * 90)

    filled_expiry = defaultdict(int)
    unfilled_expiry = defaultdict(int)
    for o in filled_orders:
        filled_expiry[categorize_expiry(o["time_to_expiry_seconds"])] += 1
    for o in unfilled_orders:
        unfilled_expiry[categorize_expiry(o["time_to_expiry_seconds"])] += 1

    print(f"  {'Expiry bucket':<15} {'Filled':>8} {'Filled%':>8} {'Unfilled':>10} {'Unfilled%':>10} {'Fill Rate':>10}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for bucket in EXPIRY_ORDER:
        fc = filled_expiry.get(bucket, 0)
        uc = unfilled_expiry.get(bucket, 0)
        total = fc + uc
        fpct = fc / len(filled_orders) * 100 if filled_orders else 0
        upct = uc / len(unfilled_orders) * 100 if unfilled_orders else 0
        fill_rate = fc / total * 100 if total > 0 else 0
        print(f"  {bucket:<15} {fc:>8} {fpct:>7.1f}% {uc:>10} {upct:>9.1f}% {fill_rate:>9.1f}%")

    # === PRICE DEVIATION ===
    print(f"\n{'=' * 90}")
    print("PRICE DEVIATION FROM MARKET (positive = order asks less than market)")
    print("=" * 90)

    filled_devs = [o["price_deviation_pct"] for o in filled_orders if o["price_deviation_pct"] is not None]
    unfilled_devs = [o["price_deviation_pct"] for o in unfilled_orders if o["price_deviation_pct"] is not None]

    if filled_devs:
        sorted_fd = sorted(filled_devs)
        print(f"\n  Filled orders ({len(filled_devs)} with price data):")
        print(f"    Min:     {min(filled_devs):>8.2f}%")
        print(f"    p10:     {sorted_fd[int(len(sorted_fd)*0.1)]:>8.2f}%")
        print(f"    p25:     {sorted_fd[int(len(sorted_fd)*0.25)]:>8.2f}%")
        print(f"    Median:  {sorted_fd[len(sorted_fd)//2]:>8.2f}%")
        print(f"    p75:     {sorted_fd[int(len(sorted_fd)*0.75)]:>8.2f}%")
        print(f"    p90:     {sorted_fd[int(len(sorted_fd)*0.9)]:>8.2f}%")
        print(f"    Max:     {max(filled_devs):>8.2f}%")
        print(f"    Mean:    {sum(filled_devs)/len(filled_devs):>8.2f}%")

    if unfilled_devs:
        sorted_ud = sorted(unfilled_devs)
        print(f"\n  Unfilled orders ({len(unfilled_devs)} with price data):")
        print(f"    Min:     {min(unfilled_devs):>8.2f}%")
        print(f"    p10:     {sorted_ud[int(len(sorted_ud)*0.1)]:>8.2f}%")
        print(f"    p25:     {sorted_ud[int(len(sorted_ud)*0.25)]:>8.2f}%")
        print(f"    Median:  {sorted_ud[len(sorted_ud)//2]:>8.2f}%")
        print(f"    p75:     {sorted_ud[int(len(sorted_ud)*0.75)]:>8.2f}%")
        print(f"    p90:     {sorted_ud[int(len(sorted_ud)*0.9)]:>8.2f}%")
        print(f"    Max:     {max(unfilled_devs):>8.2f}%")
        print(f"    Mean:    {sum(unfilled_devs)/len(unfilled_devs):>8.2f}%")

    # Deviation buckets comparison
    dev_buckets_def = [
        ("< -50%", -999999, -50),
        ("-50% to -10%", -50, -10),
        ("-10% to -1%", -10, -1),
        ("-1% to 0%", -1, 0),
        ("0% to 1%", 0, 1),
        ("1% to 5%", 1, 5),
        ("5% to 20%", 5, 20),
        ("> 20%", 20, 999999),
    ]

    print(f"\n  {'Deviation':<16} {'Filled':>8} {'Filled%':>8} {'Unfilled':>10} {'Unfilled%':>10} {'Fill Rate':>10}")
    print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for label, lo, hi in dev_buckets_def:
        fc = sum(1 for d in filled_devs if lo <= d < hi)
        uc = sum(1 for d in unfilled_devs if lo <= d < hi)
        total = fc + uc
        fpct = fc / len(filled_devs) * 100 if filled_devs else 0
        upct = uc / len(unfilled_devs) * 100 if unfilled_devs else 0
        fill_rate = fc / total * 100 if total > 0 else 0
        print(f"  {label:<16} {fc:>8} {fpct:>7.1f}% {uc:>10} {upct:>9.1f}% {fill_rate:>9.1f}%")

    # === TOKEN PAIRS ===
    print(f"\n{'=' * 90}")
    print("TOKEN PAIRS: FILLED vs UNFILLED")
    print("=" * 90)

    filled_pairs = defaultdict(int)
    unfilled_pairs = defaultdict(int)
    for o in filled_orders:
        filled_pairs[o["pair"]] += 1
    for o in unfilled_orders:
        unfilled_pairs[o["pair"]] += 1

    # Get all pairs that have at least one fill
    all_filled_pair_names = sorted(filled_pairs.keys(), key=lambda p: -filled_pairs[p])

    print(f"\n  Top filled token pairs:")
    print(f"  {'Pair':<30} {'Filled':>8} {'Unfilled':>10} {'Fill Rate':>10}")
    print(f"  {'-'*30} {'-'*8} {'-'*10} {'-'*10}")
    for pair in all_filled_pair_names[:20]:
        fc = filled_pairs[pair]
        uc = unfilled_pairs.get(pair, 0)
        total = fc + uc
        fill_rate = fc / total * 100 if total > 0 else 0
        print(f"  {pair:<30} {fc:>8} {uc:>10} {fill_rate:>9.1f}%")

    # Top unfilled-only pairs (never filled)
    never_filled = {p: c for p, c in unfilled_pairs.items() if p not in filled_pairs}
    if never_filled:
        print(f"\n  Top NEVER-FILLED token pairs (stale orders):")
        print(f"  {'Pair':<30} {'Count':>10}")
        print(f"  {'-'*30} {'-'*10}")
        for pair, count in sorted(never_filled.items(), key=lambda x: -x[1])[:15]:
            print(f"  {pair:<30} {count:>10}")

    # === ORDER SIZE ===
    print(f"\n{'=' * 90}")
    print("ORDER SIZE (estimated ETH value)")
    print("=" * 90)

    filled_sizes = [o["sell_value_eth"] for o in filled_orders if o["sell_value_eth"] is not None and o["sell_value_eth"] > 0]
    unfilled_sizes = [o["sell_value_eth"] for o in unfilled_orders if o["sell_value_eth"] is not None and o["sell_value_eth"] > 0]

    if filled_sizes:
        sorted_fs = sorted(filled_sizes)
        print(f"\n  Filled orders ({len(filled_sizes)} with size data):")
        print(f"    Min:     {min(filled_sizes):>12.4f} ETH")
        print(f"    p25:     {sorted_fs[int(len(sorted_fs)*0.25)]:>12.4f} ETH")
        print(f"    Median:  {sorted_fs[len(sorted_fs)//2]:>12.4f} ETH")
        print(f"    p75:     {sorted_fs[int(len(sorted_fs)*0.75)]:>12.4f} ETH")
        print(f"    Max:     {max(filled_sizes):>12.4f} ETH")
        print(f"    Mean:    {sum(filled_sizes)/len(filled_sizes):>12.4f} ETH")

    if unfilled_sizes:
        sorted_us = sorted(unfilled_sizes)
        print(f"\n  Unfilled orders ({len(unfilled_sizes)} with size data):")
        print(f"    Min:     {min(unfilled_sizes):>12.4f} ETH")
        print(f"    p25:     {sorted_us[int(len(sorted_us)*0.25)]:>12.4f} ETH")
        print(f"    Median:  {sorted_us[len(sorted_us)//2]:>12.4f} ETH")
        print(f"    p75:     {sorted_us[int(len(sorted_us)*0.75)]:>12.4f} ETH")
        print(f"    Max:     {max(unfilled_sizes):>12.4f} ETH")
        print(f"    Mean:    {sum(unfilled_sizes)/len(unfilled_sizes):>12.4f} ETH")

    # === PARTIALLY FILLABLE ===
    print(f"\n{'=' * 90}")
    print("PARTIALLY FILLABLE FLAG")
    print("=" * 90)

    filled_partial = sum(1 for o in filled_orders if o["partially_fillable"])
    filled_full = len(filled_orders) - filled_partial
    unfilled_partial = sum(1 for o in unfilled_orders if o["partially_fillable"])
    unfilled_full = len(unfilled_orders) - unfilled_partial

    print(f"  {'Type':<20} {'Filled':>8} {'Unfilled':>10} {'Fill Rate':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10}")
    total_full = filled_full + unfilled_full
    total_partial = filled_partial + unfilled_partial
    fr_full = filled_full / total_full * 100 if total_full > 0 else 0
    fr_partial = filled_partial / total_partial * 100 if total_partial > 0 else 0
    print(f"  {'Fill-or-kill':<20} {filled_full:>8} {unfilled_full:>10} {fr_full:>9.1f}%")
    print(f"  {'Partially fillable':<20} {filled_partial:>8} {unfilled_partial:>10} {fr_partial:>9.1f}%")

    # === ORDER KIND ===
    print(f"\n{'=' * 90}")
    print("ORDER KIND (buy vs sell)")
    print("=" * 90)

    filled_sell = sum(1 for o in filled_orders if o["kind"] == "sell")
    filled_buy = len(filled_orders) - filled_sell
    unfilled_sell = sum(1 for o in unfilled_orders if o["kind"] == "sell")
    unfilled_buy = len(unfilled_orders) - unfilled_sell

    print(f"  {'Kind':<20} {'Filled':>8} {'Unfilled':>10} {'Fill Rate':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10}")
    total_sell = filled_sell + unfilled_sell
    total_buy = filled_buy + unfilled_buy
    fr_sell = filled_sell / total_sell * 100 if total_sell > 0 else 0
    fr_buy = filled_buy / total_buy * 100 if total_buy > 0 else 0
    print(f"  {'Sell':<20} {filled_sell:>8} {unfilled_sell:>10} {fr_sell:>9.1f}%")
    print(f"  {'Buy':<20} {filled_buy:>8} {unfilled_buy:>10} {fr_buy:>9.1f}%")

    # === COMBINED SIGNAL ===
    print(f"\n{'=' * 90}")
    print("COMBINED SIGNAL: What predicts a fill?")
    print("=" * 90)

    # Check: short expiry + close to market price
    def is_likely_fill(o):
        """Heuristic: short expiry AND close to market price."""
        tte = o["time_to_expiry_seconds"]
        dev = o["price_deviation_pct"]
        if tte is not None and tte <= 600 and dev is not None and dev >= -2:
            return True
        return False

    filled_match = sum(1 for o in filled_orders if is_likely_fill(o))
    unfilled_match = sum(1 for o in unfilled_orders if is_likely_fill(o))
    total_match = filled_match + unfilled_match

    print(f"\n  Heuristic: expiry <= 10 min AND price deviation >= -2%")
    print(f"  Filled matching:     {filled_match:>8} / {len(filled_orders)} ({filled_match/len(filled_orders)*100:.1f}% recall)")
    print(f"  Unfilled matching:   {unfilled_match:>8} / {len(unfilled_orders)} ({unfilled_match/len(unfilled_orders)*100:.1f}% false positive rate)")
    if total_match > 0:
        print(f"  Precision:           {filled_match/total_match*100:.1f}% (of predicted fills, this many were actually filled)")
    print(f"  Reduction:           Would query {total_match} orders instead of {len(filled_orders)+len(unfilled_orders)} ({total_match/(len(filled_orders)+len(unfilled_orders))*100:.1f}%)")

    # Try different thresholds
    print(f"\n  Threshold sweep:")
    print(f"  {'Expiry':<12} {'Dev%':<8} {'Recall':>8} {'Precision':>10} {'Orders':>8} {'Reduction':>10}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*10}")

    total_orders = len(filled_orders) + len(unfilled_orders)
    for max_expiry in [120, 300, 600, 3600, 86400]:
        for min_dev in [-5, -2, -1, 0]:
            fm = sum(1 for o in filled_orders
                     if o["time_to_expiry_seconds"] is not None
                     and o["time_to_expiry_seconds"] <= max_expiry
                     and o["price_deviation_pct"] is not None
                     and o["price_deviation_pct"] >= min_dev)
            um = sum(1 for o in unfilled_orders
                     if o["time_to_expiry_seconds"] is not None
                     and o["time_to_expiry_seconds"] <= max_expiry
                     and o["price_deviation_pct"] is not None
                     and o["price_deviation_pct"] >= min_dev)
            tm = fm + um
            recall = fm / len(filled_orders) * 100 if filled_orders else 0
            precision = fm / tm * 100 if tm > 0 else 0
            reduction = tm / total_orders * 100 if total_orders > 0 else 0

            # Format expiry nicely
            if max_expiry < 3600:
                exp_str = f"<= {max_expiry//60}min"
            elif max_expiry < 86400:
                exp_str = f"<= {max_expiry//3600}hr"
            else:
                exp_str = f"<= {max_expiry//86400}d"

            print(f"  {exp_str:<12} {'>= '+str(min_dev)+'%':<8} {recall:>7.1f}% {precision:>9.1f}% {tm:>8} {reduction:>9.1f}%")

    # === SAMPLE FILLED ORDERS ===
    print(f"\n{'=' * 90}")
    print("SAMPLE FILLED ORDERS (last 10)")
    print("=" * 90)
    for o in filled_orders[-10:]:
        tte = o["time_to_expiry_seconds"]
        tte_str = f"{tte}s" if tte is not None else "?"
        if tte is not None:
            if tte > 86400:
                tte_str = f"{tte//86400}d"
            elif tte > 3600:
                tte_str = f"{tte//3600}h"
            elif tte > 60:
                tte_str = f"{tte//60}m"
        dev_str = f"{o['price_deviation_pct']:.1f}%" if o['price_deviation_pct'] is not None else "?"
        size_str = f"{o['sell_value_eth']:.4f} ETH" if o['sell_value_eth'] else "?"
        print(f"  Auction {o['auction_id']}: {o['pair']:<25} expiry={tte_str:<8} dev={dev_str:<8} size={size_str}")


if __name__ == "__main__":
    hours = 24
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 analyze_filled_orders.py [hours]")
            print("  Default: 24 hours. Use 0 for all data.")
            sys.exit(1)
    if hours == 0:
        hours = 999999
    analyze_filled_orders(hours)
