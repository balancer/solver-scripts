#!/usr/bin/env python3
"""
Analyze order volume from auction data to understand request patterns.
Shows orders per auction over time, hourly/daily aggregates, and token pair frequency.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime


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
    hourly_auctions = defaultdict(lambda: {"auctions": 0, "orders": 0})
    daily_auctions = defaultdict(lambda: {"auctions": 0, "orders": 0})

    for auction_file in auction_files:
        try:
            with open(auction_file) as f:
                data = json.load(f)

            orders = data.get("orders", [])
            order_count = len(orders)
            auction_id = auction_file.stem.replace("_auction", "")

            # Get timestamp from file modification time
            mtime = auction_file.stat().st_mtime
            ts = datetime.fromtimestamp(mtime)
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            day_key = ts.strftime("%Y-%m-%d")

            orders_per_auction.append({
                "auction_id": auction_id,
                "order_count": order_count,
                "timestamp": ts,
            })

            hourly_auctions[hour_key]["auctions"] += 1
            hourly_auctions[hour_key]["orders"] += order_count

            daily_auctions[day_key]["auctions"] += 1
            daily_auctions[day_key]["orders"] += order_count

            # Track token pairs
            for order in orders:
                sell_token = order.get("sell_token", order.get("sellToken", "?"))
                buy_token = order.get("buy_token", order.get("buyToken", "?"))
                pair = f"{sell_token[:10]}..→{buy_token[:10]}.."
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

    first_ts = min(a["timestamp"] for a in orders_per_auction)
    last_ts = max(a["timestamp"] for a in orders_per_auction)
    duration_hours = (last_ts - first_ts).total_seconds() / 3600

    print("=" * 80)
    print("ORDER VOLUME SUMMARY")
    print("=" * 80)
    print(f"Time range:              {first_ts.strftime('%Y-%m-%d %H:%M')} → {last_ts.strftime('%Y-%m-%d %H:%M')}")
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

    # Distribution
    print(f"\n{'=' * 80}")
    print("ORDER COUNT DISTRIBUTION")
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
        else:
            buckets["100+"] += 1

    for bucket in ["0", "1-5", "6-10", "11-25", "26-50", "51-100", "100+"]:
        count = buckets.get(bucket, 0)
        pct = count / len(order_counts) * 100
        bar = "#" * int(pct / 2)
        print(f"  {bucket:>6} orders: {count:>6} auctions ({pct:>5.1f}%) {bar}")

    # Daily breakdown
    print(f"\n{'=' * 80}")
    print("DAILY BREAKDOWN")
    print("=" * 80)
    print(f"  {'Date':<12} {'Auctions':>10} {'Orders':>10} {'Avg Ord/Auc':>12}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12}")
    for day in sorted(daily_auctions.keys()):
        d = daily_auctions[day]
        avg = d["orders"] / d["auctions"] if d["auctions"] > 0 else 0
        print(f"  {day:<12} {d['auctions']:>10} {d['orders']:>10} {avg:>12.1f}")

    # Hourly breakdown (last 24h or all if less)
    print(f"\n{'=' * 80}")
    print("HOURLY BREAKDOWN (last 24 hours)")
    print("=" * 80)
    print(f"  {'Hour':<18} {'Auctions':>10} {'Orders':>10} {'Avg Ord/Auc':>12}")
    print(f"  {'-'*18} {'-'*10} {'-'*10} {'-'*12}")
    sorted_hours = sorted(hourly_auctions.keys())
    for hour in sorted_hours[-24:]:
        h = hourly_auctions[hour]
        avg = h["orders"] / h["auctions"] if h["auctions"] > 0 else 0
        print(f"  {hour:<18} {h['auctions']:>10} {h['orders']:>10} {avg:>12.1f}")

    # Top token pairs
    print(f"\n{'=' * 80}")
    print("TOP 20 TOKEN PAIRS (by order frequency)")
    print("=" * 80)
    for pair, count in sorted(token_pairs.items(), key=lambda x: -x[1])[:20]:
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
    print(f"\nIf filtering to Balancer-relevant pairs only:")
    print(f"  (Run with actual pair filtering to estimate reduction)")


if __name__ == "__main__":
    analyze_order_volume()
