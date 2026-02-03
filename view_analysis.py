#!/usr/bin/env python3
"""
Interactive viewer for solution analysis files.
Displays analysis in a nice, readable format with multiple viewing modes.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def format_number(num_str, decimals=18):
    """Format large numbers nicely."""
    try:
        num = int(num_str)
        if decimals == 6:  # USDC
            return f"{num / 1e6:,.2f}"
        elif decimals == 8:  # WBTC
            return f"{num / 1e8:,.6f}"
        else:  # 18 decimals (WETH, DAI)
            return f"{num / 1e18:,.6f}"
    except:
        return str(num_str)

def get_token_decimals(token_name):
    """Get decimals for common tokens."""
    decimals_map = {
        'USDC': 6,
        'USDT': 6,
        'WBTC': 8,
        'WETH': 18,
        'ETH': 18,
        'DAI': 18,
        'AAVE': 18,
        'UNI': 18,
    }
    return decimals_map.get(token_name, 18)

def print_header(title, width=100):
    """Print a nice header."""
    print("\n" + "=" * width)
    print(f"{title:^{width}}")
    print("=" * width)

def print_section(title, width=100):
    """Print a section divider."""
    print(f"\n{title}")
    print("-" * width)

def view_summary(analysis_files):
    """Display summary of all analyses."""
    print_header("SOLUTION ANALYSIS SUMMARY")
    
    # Load all files
    results = []
    for file in sorted(analysis_files):
        with open(file) as f:
            results.append(json.load(f))
    
    # Calculate statistics
    total = len(results)
    valid = sum(1 for r in results if r['valid'])
    competitive = sum(1 for r in results if r['competitive'])
    beat_winner = sum(1 for r in results if r['beat_winner'])
    
    # Pool statistics
    pool_types = defaultdict(int)
    for r in results:
        for pool_type, count in r['pool_stats'].items():
            pool_types[pool_type] += count
    
    # Performance statistics
    total_surplus = sum(
        t['surplus_vs_min_pct'] 
        for r in results 
        for t in r['trades']
    )
    avg_surplus = total_surplus / total if total > 0 else 0
    
    # Display
    print(f"\n{'Metric':<40} {'Value':>15} {'Percentage':>15}")
    print("-" * 70)
    print(f"{'Total Auctions':<40} {total:>15}")
    valid_pct = f'({valid/total*100:.1f}%)'
    print(f"{'Valid Solutions':<40} {valid:>15} {valid_pct:>15}")
    comp_pct = f'({competitive/total*100:.1f}%)'
    print(f"{'Competitive (Beat Winner)':<40} {competitive:>15} {comp_pct:>15}")
    beat_pct = f'({beat_winner/total*100:.1f}%)'
    print(f"{'Beat Winner Output':<40} {beat_winner:>15} {beat_pct:>15}")
    avg_str = f'{avg_surplus:.2f}%'
    print(f"{'Average Surplus vs User Min':<40} {avg_str:>15}")
    
    print_section("Pool Usage Statistics")
    print(f"{'Pool Type':<30} {'Count':>15} {'Percentage':>15}")
    print("-" * 60)
    total_pools = sum(pool_types.values())
    for pool_type, count in sorted(pool_types.items(), key=lambda x: -x[1]):
        pool_pct = f'({count/total_pools*100:.1f}%)'
        print(f"{pool_type:<30} {count:>15} {pool_pct:>15}")
    
    # Win/Loss breakdown
    print_section("Performance Breakdown")
    wins = [r for r in results if r['beat_winner']]
    losses = [r for r in results if not r['beat_winner']]
    
    if wins:
        print(f"\n✓ WE BEAT THE WINNER ({len(wins)} auctions):")
        for r in wins:
            trade = r['trades'][0]
            print(f"  • Auction {r['auction_id']}: "
                  f"{trade['sell_token_name']}→{trade['buy_token_name']} "
                  f"(+{trade['diff_vs_winner_pct']:.2f}% better)")
    
    if losses:
        print(f"\n✗ WINNER BEAT US ({len(losses)} auctions):")
        for r in losses:
            trade = r['trades'][0]
            print(f"  • Auction {r['auction_id']}: "
                  f"{trade['sell_token_name']}→{trade['buy_token_name']} "
                  f"({trade['diff_vs_winner_pct']:.2f}% behind)")

def view_detailed_list(analysis_files):
    """Display detailed list of all analyses."""
    print_header("DETAILED ANALYSIS LIST")
    
    # Table header
    print(f"\n{'Auction':<12} {'Valid':>7} {'Win':>7} {'Surplus':>10} "
          f"{'Pool':>18} {'Trade':>20} {'Rank':>8}")
    print("-" * 90)
    
    for file in sorted(analysis_files):
        with open(file) as f:
            data = json.load(f)
        
        valid_icon = "✓" if data['valid'] else "✗"
        win_icon = "🏆" if data['beat_winner'] else "✗"
        
        trade = data['trades'][0] if data['trades'] else {}
        surplus = f"{trade.get('surplus_vs_min_pct', 0):+.2f}%"
        pool_type = list(data['pool_stats'].keys())[0] if data['pool_stats'] else "N/A"
        trade_pair = f"{trade.get('sell_token_name', '?')}→{trade.get('buy_token_name', '?')}"
        rank = f"Rank {trade.get('winner_ranking', '?')}"
        
        print(f"{data['auction_id']:<12} {valid_icon:>7} {win_icon:>7} {surplus:>10} "
              f"{pool_type:>18} {trade_pair:>20} {rank:>8}")

def view_individual(analysis_file):
    """Display detailed view of a single analysis."""
    with open(analysis_file) as f:
        data = json.load(f)
    
    auction_id = data['auction_id']
    print_header(f"AUCTION {auction_id} - DETAILED ANALYSIS")
    
    # Status badges
    status = []
    if data['valid']:
        status.append("✓ VALID")
    else:
        status.append("✗ INVALID")
    
    if data['competitive']:
        status.append("🏆 COMPETITIVE")
    
    if data['beat_winner']:
        status.append("👑 BEAT WINNER")
    
    print(f"\nStatus: {' | '.join(status)}")
    print(f"Solution ID: {data['solution_id']}")
    print(f"Gas Estimate: {data['gas']:,}")
    print(f"Interactions: {data['num_interactions']}")
    print(f"Trades: {data['num_trades']}")
    
    # Pool interactions
    print_section("POOL INTERACTIONS", 100)
    for i, interaction in enumerate(data['interactions'], 1):
        print(f"\nInteraction {i}:")
        print(f"  Pool ID: {interaction['pool_id']}")
        print(f"  Type: {interaction['pool_kind']}")
        print(f"  Address: {interaction['pool_address']}")
        print(f"  Fee: {interaction['pool_fee']}")
        
        in_decimals = get_token_decimals(interaction['input_token_name'])
        out_decimals = get_token_decimals(interaction['output_token_name'])
        
        in_amount = format_number(interaction['input_amount'], in_decimals)
        out_amount = format_number(interaction['output_amount'], out_decimals)
        
        print(f"\n  Route:")
        print(f"    {interaction['input_token_name']:>8} ({in_amount:>15})")
        print(f"         ↓")
        print(f"    {interaction['output_token_name']:>8} ({out_amount:>15})")
    
    # Trade results
    print_section("TRADE RESULTS", 100)
    for i, trade in enumerate(data['trades'], 1):
        print(f"\nTrade {i}:")
        print(f"  Order ID: {trade['order_id'][:50]}...")
        print(f"  Trade Pair: {trade['sell_token_name']} → {trade['buy_token_name']}")
        
        sell_decimals = get_token_decimals(trade['sell_token_name'])
        buy_decimals = get_token_decimals(trade['buy_token_name'])
        
        sell_amount = format_number(trade['sell_amount'], sell_decimals)
        print(f"\n  Sell: {sell_amount} {trade['sell_token_name']}")
        
        required = format_number(trade['buy_amount_required'], buy_decimals)
        our_output = format_number(trade['our_output'], buy_decimals)
        
        print(f"\n  {'Requirement':<25} {'Amount':>20} {'Status':>15}")
        print(f"  {'-'*60}")
        print(f"  {'User Minimum':<25} {required:>20} {trade['buy_token_name']:>15}")
        print(f"  {'Our Output':<25} {our_output:>20} {trade['buy_token_name']:>15}")
        
        surplus = format_number(trade['surplus_vs_min'], buy_decimals)
        surplus_pct = trade['surplus_vs_min_pct']
        
        if trade['valid']:
            pct_display = f'(+{surplus_pct:.2f}%)'
            print(f"  {'Surplus':<25} {surplus:>20} {pct_display:>15} ✓")
        else:
            pct_display = f'({surplus_pct:.2f}%)'
            print(f"  {'Deficit':<25} {surplus:>20} {pct_display:>15} ✗")
        
        # Winner comparison
        if 'winner_output' in trade and trade['winner_output'] != '0':
            print(f"\n  {'Comparison vs Winner':<25}")
            print(f"  {'-'*60}")
            
            winner_output = format_number(trade['winner_output'], buy_decimals)
            diff = format_number(trade['diff_vs_winner'], buy_decimals)
            diff_pct = trade['diff_vs_winner_pct']
            
            print(f"  {'Winner Output':<25} {winner_output:>20} {trade['buy_token_name']:>15}")
            winner_rank = f"Rank {trade['winner_ranking']}"
            print(f"  {'Winner Ranking':<25} {winner_rank:>20}")
            
            if trade['beat_winner']:
                pct_str = f'(+{diff_pct:.2f}%)'
                print(f"  {'Our Advantage':<25} {diff:>20} {pct_str:>15} 🏆")
            else:
                pct_str = f'({diff_pct:.2f}%)'
                print(f"  {'Their Advantage':<25} {diff:>20} {pct_str:>15}")
        
        # Execution details
        print(f"\n  {'Execution Details':<25}")
        print(f"  {'-'*60}")
        exec_amount = format_number(trade['executed_amount'], sell_decimals)
        fee_amount = format_number(trade['fee'], sell_decimals)
        print(f"  {'Executed Amount':<25} {exec_amount:>20} {trade['sell_token_name']:>15}")
        print(f"  {'Fee':<25} {fee_amount:>20} {trade['sell_token_name']:>15}")
    
    # Clearing prices
    if data['prices']:
        print_section("CLEARING PRICES", 100)
        for token, price in data['prices'].items():
            # Determine token name from address
            token_name = "Unknown"
            for t in data['trades']:
                if t['sell_token'] == token:
                    token_name = t['sell_token_name']
                elif t['buy_token'] == token:
                    token_name = t['buy_token_name']
            
            print(f"  {token_name:>8}: {price}")

def view_pools(analysis_files):
    """Display pool usage analysis."""
    print_header("POOL USAGE ANALYSIS")
    
    # Aggregate pool data
    pool_data = {}
    
    for file in analysis_files:
        with open(file) as f:
            data = json.load(f)
        
        for interaction in data['interactions']:
            pool_addr = interaction['pool_address']
            
            if pool_addr not in pool_data:
                pool_data[pool_addr] = {
                    'address': pool_addr,
                    'kind': interaction['pool_kind'],
                    'fee': interaction['pool_fee'],
                    'uses': 0,
                    'wins': 0,
                    'total_surplus': 0,
                    'auctions': []
                }
            
            pool_data[pool_addr]['uses'] += 1
            pool_data[pool_addr]['auctions'].append(data['auction_id'])
            
            if data['beat_winner']:
                pool_data[pool_addr]['wins'] += 1
            
            if data['trades']:
                pool_data[pool_addr]['total_surplus'] += data['trades'][0]['surplus_vs_min_pct']
    
    # Display pool statistics
    print(f"\n{'Pool Address':<44} {'Type':>18} {'Fee':>8} {'Uses':>6} {'Wins':>6} {'Win%':>8} {'Avg Surplus':>12}")
    print("-" * 120)
    
    for pool in sorted(pool_data.values(), key=lambda x: -x['uses']):
        win_pct = (pool['wins'] / pool['uses'] * 100) if pool['uses'] > 0 else 0
        avg_surplus = pool['total_surplus'] / pool['uses'] if pool['uses'] > 0 else 0
        
        print(f"{pool['address']:<44} {pool['kind']:>18} {pool['fee']:>8} "
              f"{pool['uses']:>6} {pool['wins']:>6} {win_pct:>7.0f}% {avg_surplus:>11.2f}%")
    
    # Show top performing pool details
    print_section("TOP POOL DETAILS", 120)
    
    top_pool = max(pool_data.values(), key=lambda x: x['uses'])
    print(f"\nMost Used Pool:")
    print(f"  Address: {top_pool['address']}")
    print(f"  Type: {top_pool['kind']}")
    print(f"  Fee: {top_pool['fee']}")
    print(f"  Uses: {top_pool['uses']}")
    win_rate = top_pool['wins']/top_pool['uses']*100
    print(f"  Wins: {top_pool['wins']} ({win_rate:.0f}%)")
    print(f"  Auctions: {', '.join(top_pool['auctions'])}")

def main():
    """Main viewer function."""
    auction_dir = Path("auction-data/mainnet")
    analysis_files = list(auction_dir.glob("*_analysis.json"))
    
    if not analysis_files:
        print("No analysis files found!")
        print(f"Run 'python3 compare_solutions_detailed.py' first to generate analysis files.")
        return
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'summary':
            view_summary(analysis_files)
        elif command == 'list':
            view_detailed_list(analysis_files)
        elif command == 'pools':
            view_pools(analysis_files)
        elif command.startswith('auction'):
            # View specific auction
            if len(sys.argv) > 2:
                auction_id = sys.argv[2]
                analysis_file = auction_dir / f"{auction_id}_analysis.json"
                if analysis_file.exists():
                    view_individual(analysis_file)
                else:
                    print(f"Analysis file not found: {analysis_file}")
            else:
                print("Please specify auction ID: python3 view_analysis.py auction 11732945")
        elif command == 'help':
            print_help()
        else:
            print(f"Unknown command: {command}")
            print_help()
    else:
        # Default: show summary
        view_summary(analysis_files)
        print("\n" + "=" * 100)
        print("💡 TIP: Run with 'list', 'pools', or 'auction <id>' for more details")
        print("   Example: python3 view_analysis.py auction 11732945")
        print("   See all options: python3 view_analysis.py help")

def print_help():
    """Print help message."""
    print_header("ANALYSIS VIEWER - HELP")
    print("""
Usage: python3 view_analysis.py [command] [options]

Commands:
  summary             Show overall summary statistics (default)
  list                Show detailed list of all auctions
  pools               Show pool usage statistics
  auction <id>        Show detailed analysis for specific auction
  help                Show this help message

Examples:
  python3 view_analysis.py
  python3 view_analysis.py summary
  python3 view_analysis.py list
  python3 view_analysis.py pools
  python3 view_analysis.py auction 11732945

The script displays analysis from *_analysis.json files in auction-data/mainnet/
Run 'python3 compare_solutions_detailed.py' first to generate these files.
""")

if __name__ == "__main__":
    main()

