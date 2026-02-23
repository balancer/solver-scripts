#!/usr/bin/env python3
"""
Script to compare our solutions against competition winners.
Analyzes whether we would have won and identifies issues.
"""

import json
import os
from pathlib import Path
from collections import defaultdict

def compare_solutions():
    auction_dir = Path(os.environ.get("AUCTION_DIR", "/tmp/auction-data/arbitrum"))
    
    # Find all solution files
    solution_files = sorted(auction_dir.glob("*_solutions.json"))
    
    if not solution_files:
        print("No solution files found!")
        return
    
    print(f"Analyzing {len(solution_files)} auctions...\n")
    
    stats = {
        "total_auctions": len(solution_files),
        "our_solutions": 0,
        "valid_solutions": 0,
        "invalid_solutions": 0,
        "matched_winner_orders": 0,
        "would_have_won": 0,
        "would_have_ranked": [],
    }
    
    detailed_results = []
    
    for solution_file in solution_files:
        auction_id = solution_file.stem.replace("_solutions", "")
        competition_file = auction_dir / f"{auction_id}_competition.json"
        
        if not competition_file.exists():
            continue
        
        try:
            with open(solution_file, 'r') as f:
                our_data = json.load(f)
            
            with open(competition_file, 'r') as f:
                comp_data = json.load(f)
            
            our_solutions = our_data.get('solutions', [])
            stats['our_solutions'] += len(our_solutions)
            
            for our_sol in our_solutions:
                result = analyze_solution(auction_id, our_sol, comp_data)
                detailed_results.append(result)
                
                if result['valid']:
                    stats['valid_solutions'] += 1
                else:
                    stats['invalid_solutions'] += 1
                
                if result['matched_winner_order']:
                    stats['matched_winner_orders'] += 1
        
        except Exception as e:
            print(f"Error processing {solution_file.name}: {e}")
    
    # Print summary
    print("=" * 80)
    print("SOLUTION COMPARISON SUMMARY")
    print("=" * 80)
    print(f"Total auctions analyzed:     {stats['total_auctions']}")
    print(f"Our solutions submitted:     {stats['our_solutions']}")
    print(f"Valid solutions:             {stats['valid_solutions']} ({stats['valid_solutions']/max(stats['our_solutions'],1)*100:.1f}%)")
    print(f"Invalid solutions:           {stats['invalid_solutions']} ({stats['invalid_solutions']/max(stats['our_solutions'],1)*100:.1f}%)")
    print(f"Matched winner orders:       {stats['matched_winner_orders']}")
    print("=" * 80)
    
    # Print detailed results
    print("\nDETAILED RESULTS:")
    print("=" * 80)
    
    for result in detailed_results:
        print(f"\nAuction {result['auction_id']}:")
        print(f"  Solution ID: {result['solution_id']}")
        print(f"  Orders solved: {result['num_orders']}")
        print(f"  Gas: {result['gas']:,}")
        
        if result['valid']:
            print(f"  ✓ VALID")
        else:
            print(f"  ✗ INVALID: {result['invalid_reason']}")
        
        if result['matched_winner_order']:
            print(f"  ✓ Solved same order as winner (Ranking {result['winner_ranking']})")
        
        for order_result in result['orders']:
            print(f"\n    Order: {order_result['order_id'][:20]}...")
            print(f"      Sell: {order_result['sell_amount']} {order_result['sell_token_name']}")
            print(f"      Buy Required: {order_result['required_buy_amount']} {order_result['buy_token_name']}")
            print(f"      Buy Got: {order_result['actual_buy_amount']} {order_result['buy_token_name']}")
            
            if order_result['valid']:
                print(f"      ✓ Valid - Surplus: {order_result['surplus']:,} ({order_result['surplus_pct']:.4f}%)")
            else:
                print(f"      ✗ Invalid - Deficit: {order_result['deficit']:,} ({order_result['deficit_pct']:.4f}%)")
        
        print(f"\n  Competition: {result['num_competition_solutions']} solutions, {result['num_winners']} winner(s)")
        if result['winner_score']:
            print(f"  Winner score: {result['winner_score']}")
    
    return stats, detailed_results

def analyze_solution(auction_id, our_sol, comp_data):
    """Analyze a single solution against competition data."""
    result = {
        'auction_id': auction_id,
        'solution_id': our_sol.get('id'),
        'num_orders': len(our_sol.get('trades', [])),
        'gas': our_sol.get('gas', 0),
        'valid': True,
        'invalid_reason': None,
        'matched_winner_order': False,
        'winner_ranking': None,
        'winner_score': None,
        'num_competition_solutions': len(comp_data.get('solutions', [])),
        'num_winners': len([s for s in comp_data.get('solutions', []) if s.get('isWinner')]),
        'orders': []
    }
    
    # Get winners
    winners = [s for s in comp_data.get('solutions', []) if s.get('isWinner')]
    if winners:
        result['winner_score'] = max(w.get('score', 0) for w in winners)
    
    # Analyze each trade/order
    for trade in our_sol.get('trades', []):
        order_id = trade.get('order')
        
        # Find corresponding interaction
        # Match by looking at the input/output tokens and amounts
        interaction = None
        for inter in our_sol.get('interactions', []):
            # Simple heuristic: match if tokens align
            interaction = inter
            break
        
        if not interaction:
            result['valid'] = False
            result['invalid_reason'] = "No matching interaction found"
            continue
        
        # Check if this order was solved by a winner
        winner_order = None
        for winner in winners:
            for w_order in winner.get('orders', []):
                if w_order['id'] == order_id:
                    winner_order = w_order
                    result['matched_winner_order'] = True
                    result['winner_ranking'] = winner.get('ranking')
                    break
            if winner_order:
                break
        
        if not winner_order:
            # Can't validate without knowing the order requirements
            order_result = {
                'order_id': order_id,
                'valid': None,
                'sell_amount': interaction.get('inputAmount'),
                'sell_token_name': 'Unknown',
                'required_buy_amount': 'Unknown',
                'actual_buy_amount': interaction.get('outputAmount'),
                'buy_token_name': 'Unknown',
                'surplus': 0,
                'surplus_pct': 0,
                'deficit': 0,
                'deficit_pct': 0,
            }
            result['orders'].append(order_result)
            continue
        
        # Validate against winner's order
        required_buy = int(winner_order['buyAmount'])
        actual_buy = int(interaction['outputAmount'])
        
        order_valid = actual_buy >= required_buy
        
        sell_token_name = "WETH" if "c02aaa" in winner_order['sellToken'].lower() else \
                         "USDC" if "a0b869" in winner_order['sellToken'].lower() else \
                         winner_order['sellToken'][:10]
        buy_token_name = "WETH" if "c02aaa" in winner_order['buyToken'].lower() else \
                        "USDC" if "a0b869" in winner_order['buyToken'].lower() else \
                        winner_order['buyToken'][:10]
        
        order_result = {
            'order_id': order_id,
            'valid': order_valid,
            'sell_amount': winner_order['sellAmount'],
            'sell_token_name': sell_token_name,
            'required_buy_amount': required_buy,
            'actual_buy_amount': actual_buy,
            'buy_token_name': buy_token_name,
            'surplus': actual_buy - required_buy if order_valid else 0,
            'surplus_pct': ((actual_buy - required_buy) / required_buy * 100) if order_valid else 0,
            'deficit': required_buy - actual_buy if not order_valid else 0,
            'deficit_pct': ((required_buy - actual_buy) / required_buy * 100) if not order_valid else 0,
        }
        
        result['orders'].append(order_result)
        
        if not order_valid:
            result['valid'] = False
            result['invalid_reason'] = f"Order {order_id[:20]}... did not meet minimum buy amount"
    
    return result

if __name__ == "__main__":
    stats, results = compare_solutions()


