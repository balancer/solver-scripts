#!/usr/bin/env python3
"""
Enhanced script to compare our solutions against competition winners with detailed analysis.
Shows Balancer pools used, token pairs, pricing, and comprehensive statistics.
"""

import json
from pathlib import Path
from collections import defaultdict, Counter

def format_token_name(address):
    """Convert token address to readable name."""
    address_lower = address.lower()
    token_map = {
        '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': 'WETH',
        '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
        '0x6b175474e89094c44da98b954eedeac495271d0f': 'DAI',
        '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',
        '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'WBTC',
        '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'AAVE',
        '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'UNI',
        '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': 'ETH',
    }
    return token_map.get(address_lower, address[:10] + '...')

def format_amount(amount, decimals=18):
    """Format token amount with proper decimals."""
    try:
        val = int(amount) / (10 ** decimals)
        if val >= 1000000:
            return f"{val/1000000:.2f}M"
        elif val >= 1000:
            return f"{val/1000:.2f}K"
        else:
            return f"{val:.6f}"
    except:
        return str(amount)

def load_auction_data(auction_dir, auction_id):
    """Load all data for a given auction."""
    data = {}
    
    files = {
        'auction': f"{auction_id}_auction.json",
        'solutions': f"{auction_id}_solutions.json",
        'competition': f"{auction_id}_competition.json",
        'liquidity': f"{auction_id}_liquidity.json",
    }
    
    for key, filename in files.items():
        filepath = auction_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                data[key] = json.load(f)
        else:
            data[key] = None
    
    return data

def get_pool_info(liquidity_data, pool_id):
    """Get detailed pool information from liquidity data."""
    if not liquidity_data:
        return None
    
    for pool in liquidity_data.get('liquidity', []):
        if pool.get('id') == pool_id:
            return {
                'id': pool.get('id'),
                'kind': pool.get('kind', 'unknown'),
                'address': pool.get('address'),
                'balancer_pool_id': pool.get('balancerPoolId'),
                'fee': pool.get('fee'),
                'gas_estimate': pool.get('gasEstimate'),
                'tokens': list(pool.get('tokens', {}).keys()),
                'token_count': len(pool.get('tokens', {})),
            }
    
    return None

def analyze_solution_detailed(auction_id, data):
    """Perform detailed analysis of a solution."""
    our_sol = data['solutions'].get('solutions', [{}])[0]
    auction_orders = {o['uid']: o for o in data['auction'].get('orders', [])}
    comp_data = data['competition']
    liquidity_data = data['liquidity']
    
    result = {
        'auction_id': auction_id,
        'solution_id': our_sol.get('id'),
        'gas': our_sol.get('gas', 0),
        'num_interactions': len(our_sol.get('interactions', [])),
        'num_trades': len(our_sol.get('trades', [])),
        'prices': our_sol.get('prices', {}),
        'interactions': [],
        'trades': [],
        'pool_stats': {},
        'valid': True,
        'competitive': False,
        'beat_winner': False,
    }
    
    # Get winners
    winners = [s for s in comp_data.get('solutions', []) if s.get('isWinner')]
    winner_orders = {}
    for winner in winners:
        for order in winner.get('orders', []):
            winner_orders[order['id']] = {
                'order': order,
                'winner': winner,
            }
    
    # Analyze interactions (pool usage)
    for interaction in our_sol.get('interactions', []):
        pool_id = interaction.get('id')
        pool_info = get_pool_info(liquidity_data, pool_id)
        
        interaction_detail = {
            'pool_id': pool_id,
            'pool_info': pool_info,
            'input_token': interaction.get('inputToken'),
            'output_token': interaction.get('outputToken'),
            'input_amount': interaction.get('inputAmount'),
            'output_amount': interaction.get('outputAmount'),
            'input_token_name': format_token_name(interaction.get('inputToken', '')),
            'output_token_name': format_token_name(interaction.get('outputToken', '')),
            'kind': interaction.get('kind'),
            'internalize': interaction.get('internalize'),
        }
        
        result['interactions'].append(interaction_detail)
        
        # Track pool usage stats
        if pool_info:
            pool_kind = pool_info['kind']
            if pool_kind not in result['pool_stats']:
                result['pool_stats'][pool_kind] = 0
            result['pool_stats'][pool_kind] += 1
    
    # Analyze trades (orders fulfilled)
    for trade in our_sol.get('trades', []):
        order_id = trade.get('order')
        auction_order = auction_orders.get(order_id)
        winner_info = winner_orders.get(order_id)
        
        if not auction_order:
            continue
        
        trade_detail = {
            'order_id': order_id,
            'kind': trade.get('kind'),
            'executed_amount': int(trade.get('executedAmount', 0)),
            'fee': int(trade.get('fee', 0)),
        }
        
        # Get order requirements
        sell_token = auction_order['sellToken']
        buy_token = auction_order['buyToken']
        sell_amount = int(auction_order['sellAmount'])
        buy_amount_min = int(auction_order['buyAmount'])
        is_partially_fillable = auction_order.get('partiallyFillable', False)
        executed_amount = trade_detail['executed_amount']
        
        # For partially fillable orders, prorate the minimum buy amount based on executed sell amount
        if is_partially_fillable and sell_amount > 0:
            # Prorate the minimum buy amount proportionally to the executed sell amount
            prorated_buy_min = (buy_amount_min * executed_amount) // sell_amount
            effective_buy_min = prorated_buy_min
        else:
            # For non-partial orders, must meet full minimum
            effective_buy_min = buy_amount_min
        
        trade_detail.update({
            'sell_token': sell_token,
            'buy_token': buy_token,
            'sell_token_name': format_token_name(sell_token),
            'buy_token_name': format_token_name(buy_token),
            'sell_amount': sell_amount,
            'buy_amount_required': buy_amount_min,
            'is_partially_fillable': is_partially_fillable,
            'effective_buy_min': effective_buy_min,
        })
        
        # Find our actual output from interactions
        our_output = 0
        for interaction in result['interactions']:
            if interaction['output_token'] == buy_token:
                our_output = int(interaction['output_amount'])
                break
        
        trade_detail['our_output'] = our_output
        trade_detail['valid'] = our_output >= effective_buy_min
        trade_detail['surplus_vs_min'] = our_output - effective_buy_min
        trade_detail['surplus_vs_min_pct'] = ((our_output - effective_buy_min) / effective_buy_min * 100) if effective_buy_min > 0 else 0
        
        # Compare with winner
        if winner_info:
            winner_output = int(winner_info['order']['buyAmount'])
            winner_ranking = winner_info['winner'].get('ranking')
            winner_score = winner_info['winner'].get('score')
            
            trade_detail.update({
                'winner_output': winner_output,
                'winner_ranking': winner_ranking,
                'winner_score': winner_score,
                'diff_vs_winner': our_output - winner_output,
                'diff_vs_winner_pct': ((our_output - winner_output) / winner_output * 100) if winner_output > 0 else 0,
                'beat_winner': our_output >= winner_output,
            })
            
            if our_output >= winner_output:
                result['beat_winner'] = True
        
        if not trade_detail['valid']:
            result['valid'] = False
        
        result['trades'].append(trade_detail)
    
    # Overall competitiveness
    result['competitive'] = result['valid'] and result['beat_winner']
    
    return result

def print_detailed_analysis(results):
    """Print comprehensive analysis with all details."""
    
    # Overall statistics
    total = len(results)
    valid = sum(1 for r in results if r['valid'])
    competitive = sum(1 for r in results if r['competitive'])
    beat_winner = sum(1 for r in results if r['beat_winner'])
    
    # Pool statistics
    all_pool_types = Counter()
    for result in results:
        for pool_type, count in result['pool_stats'].items():
            all_pool_types[pool_type] += count
    
    print("=" * 100)
    print("COMPREHENSIVE SOLUTION ANALYSIS")
    print("=" * 100)
    print(f"\n{'OVERALL STATISTICS':^100}")
    print("-" * 100)
    print(f"Total Auctions:              {total}")
    print(f"Valid Solutions:             {valid:3d} ({valid/total*100:5.1f}%) - Can execute on-chain")
    print(f"Competitive Solutions:       {competitive:3d} ({competitive/total*100:5.1f}%) - Valid AND beat winner")
    print(f"Beat Winner:                 {beat_winner:3d} ({beat_winner/total*100:5.1f}%) - Provided more output")
    
    print(f"\n{'BALANCER POOL USAGE':^100}")
    print("-" * 100)
    total_pool_usages = sum(all_pool_types.values())
    for pool_type, count in all_pool_types.most_common():
        pct = count / total_pool_usages * 100
        print(f"{pool_type:20s}: {count:3d} uses ({pct:5.1f}%)")
    
    print(f"\n{'=' * 100}")
    print("DETAILED AUCTION ANALYSIS")
    print("=" * 100)
    
    for result in results:
        auction_id = result['auction_id']
        
        print(f"\n{'┌' + '─' * 98 + '┐'}")
        print(f"│ {'Auction ' + auction_id:^97s}│")
        print(f"{'└' + '─' * 98 + '┘'}")
        
        # Status
        status_symbols = []
        if result['valid']:
            status_symbols.append("✓ VALID")
        else:
            status_symbols.append("✗ INVALID")
        
        if result['beat_winner']:
            status_symbols.append("🏆 BEAT WINNER")
        
        print(f"Status: {' | '.join(status_symbols)}")
        print(f"Solution ID: {result['solution_id']} | Gas: {result['gas']:,}")
        
        # Pool usage
        print(f"\n{'POOLS USED':^100}")
        print("-" * 100)
        for interaction in result['interactions']:
            pool_info = interaction['pool_info']
            if pool_info:
                print(f"Pool {interaction['pool_id']:>3s}: {pool_info['kind']:>15s}")
                print(f"  Address: {pool_info['address']}")
                print(f"  Balancer Pool ID: {pool_info['balancer_pool_id']}")
                print(f"  Fee: {pool_info['fee']}")
                print(f"  Tokens: {pool_info['token_count']} tokens")
                print(f"  Route: {interaction['input_token_name']} ({format_amount(interaction['input_amount'])}) → "
                      f"{interaction['output_token_name']} ({format_amount(interaction['output_amount'])})")
            else:
                print(f"Pool {interaction['pool_id']}: [Info not available]")
                print(f"  Route: {interaction['input_token_name']} → {interaction['output_token_name']}")
        
        # Trade results
        print(f"\n{'TRADE RESULTS':^100}")
        print("-" * 100)
        for trade in result['trades']:
            print(f"Order: {trade['order_id'][:30]}...")
            print(f"  Trade: Sell {format_amount(trade['sell_amount'])} {trade['sell_token_name']} → "
                  f"Buy {trade['buy_token_name']}")
            print(f"  User Minimum:        {trade['buy_amount_required']:>20,}")
            print(f"  Our Output:          {trade['our_output']:>20,}")
            
            if trade['valid']:
                print(f"  Surplus vs Min:      {trade['surplus_vs_min']:>+20,} ({trade['surplus_vs_min_pct']:>+6.2f}%) ✓")
            else:
                print(f"  Deficit vs Min:      {trade['surplus_vs_min']:>+20,} ({trade['surplus_vs_min_pct']:>+6.2f}%) ✗")
            
            if 'winner_output' in trade:
                print(f"  Winner Output:       {trade['winner_output']:>20,} (Rank {trade['winner_ranking']})")
                print(f"  Diff vs Winner:      {trade['diff_vs_winner']:>+20,} ({trade['diff_vs_winner_pct']:>+6.2f}%)",
                      "🏆" if trade['beat_winner'] else "")
            
            print(f"  Executed Amount:     {trade['executed_amount']:>20,}")
            print(f"  Fee Charged:         {trade['fee']:>20,}")
        
        # Prices
        if result['prices']:
            print(f"\n{'CLEARING PRICES':^100}")
            print("-" * 100)
            for token, price in result['prices'].items():
                token_name = format_token_name(token)
                print(f"  {token_name:>8s}: {price}")
    
    # Summary table
    print(f"\n{'=' * 100}")
    print(f"{'PERFORMANCE SUMMARY TABLE':^100}")
    print("=" * 100)
    print(f"{'Auction':<12} {'Valid':>7} {'Beat':>7} {'Surplus%':>10} {'Pool Type':>15} {'Winner Rank':>12}")
    print("-" * 100)
    
    for result in results:
        valid_str = "✓" if result['valid'] else "✗"
        beat_str = "✓" if result['beat_winner'] else "✗"
        
        surplus_pct = "N/A"
        pool_type = "N/A"
        winner_rank = "N/A"
        
        if result['trades']:
            trade = result['trades'][0]
            surplus_pct = f"{trade['surplus_vs_min_pct']:+6.2f}%"
            if 'winner_ranking' in trade:
                winner_rank = f"Rank {trade['winner_ranking']}"
        
        if result['pool_stats']:
            pool_type = list(result['pool_stats'].keys())[0]
        
        print(f"{result['auction_id']:<12} {valid_str:>7} {beat_str:>7} {surplus_pct:>10} {pool_type:>15} {winner_rank:>12}")

def save_analysis_to_json(result, auction_dir):
    """Save detailed analysis for a single auction to JSON file."""
    auction_id = result['auction_id']
    output_file = auction_dir / f"{auction_id}_analysis.json"
    
    # Convert result to JSON-serializable format
    json_result = {
        'auction_id': result['auction_id'],
        'solution_id': result['solution_id'],
        'gas': result['gas'],
        'num_interactions': result['num_interactions'],
        'num_trades': result['num_trades'],
        'valid': result['valid'],
        'competitive': result['competitive'],
        'beat_winner': result['beat_winner'],
        'prices': result['prices'],
        'pool_stats': result['pool_stats'],
        'interactions': [
            {
                'pool_id': i['pool_id'],
                'pool_kind': i['pool_info']['kind'] if i['pool_info'] else 'unknown',
                'pool_address': i['pool_info']['address'] if i['pool_info'] else None,
                'pool_fee': i['pool_info']['fee'] if i['pool_info'] else None,
                'input_token': i['input_token'],
                'input_token_name': i['input_token_name'],
                'input_amount': i['input_amount'],
                'output_token': i['output_token'],
                'output_token_name': i['output_token_name'],
                'output_amount': i['output_amount'],
                'kind': i['kind'],
                'internalize': i['internalize'],
            }
            for i in result['interactions']
        ],
        'trades': [
            {
                'order_id': t['order_id'],
                'sell_token': t['sell_token'],
                'sell_token_name': t['sell_token_name'],
                'sell_amount': str(t['sell_amount']),
                'buy_token': t['buy_token'],
                'buy_token_name': t['buy_token_name'],
                'buy_amount_required': str(t['buy_amount_required']),
                'is_partially_fillable': t.get('is_partially_fillable', False),
                'effective_buy_min': str(t.get('effective_buy_min', t['buy_amount_required'])),
                'our_output': str(t['our_output']),
                'valid': t['valid'],
                'surplus_vs_min': str(t['surplus_vs_min']),
                'surplus_vs_min_pct': t['surplus_vs_min_pct'],
                'winner_output': str(t.get('winner_output', 0)),
                'winner_ranking': t.get('winner_ranking'),
                'winner_score': str(t.get('winner_score', 0)),
                'diff_vs_winner': str(t.get('diff_vs_winner', 0)),
                'diff_vs_winner_pct': t.get('diff_vs_winner_pct', 0),
                'beat_winner': t.get('beat_winner', False),
                'executed_amount': str(t['executed_amount']),
                'fee': str(t['fee']),
            }
            for t in result['trades']
        ]
    }
    
    with open(output_file, 'w') as f:
        json.dump(json_result, f, indent=2)
    
    return output_file

def compare_solutions_detailed():
    auction_dir = Path("auction-data/mainnet")
    
    # Find all solution files
    solution_files = sorted(auction_dir.glob("*_solutions.json"))
    
    if not solution_files:
        print("No solution files found!")
        return
    
    print(f"Loading and analyzing {len(solution_files)} auctions...\n")
    
    results = []
    saved_files = []
    
    for solution_file in solution_files:
        auction_id = solution_file.stem.replace("_solutions", "")
        
        try:
            data = load_auction_data(auction_dir, auction_id)
            
            if not all([data['solutions'], data['auction'], data['competition']]):
                continue
            
            result = analyze_solution_detailed(auction_id, data)
            results.append(result)
            
            # Save to JSON file
            output_file = save_analysis_to_json(result, auction_dir)
            saved_files.append(output_file)
        
        except Exception as e:
            print(f"Error processing {auction_id}: {e}")
            import traceback
            traceback.print_exc()
    
    print_detailed_analysis(results)
    
    # Print saved files summary
    print(f"\n{'=' * 100}")
    print(f"{'SAVED ANALYSIS FILES':^100}")
    print("=" * 100)
    print(f"Total files saved: {len(saved_files)}")
    print("\nFiles created:")
    for filepath in saved_files:
        print(f"  ✓ {filepath.name}")
    
    return results

if __name__ == "__main__":
    results = compare_solutions_detailed()

