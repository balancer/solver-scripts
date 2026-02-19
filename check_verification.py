#!/usr/bin/env python3
"""
Script to analyze solution verification files and check for errors and accuracy.
"""

import json
import os
from pathlib import Path
from collections import defaultdict

def check_verifications():
    auction_dir = Path(os.environ.get("AUCTION_DIR", "/tmp/auction-data/arbitrum"))
    
    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return
    
    # Find all verification files
    verification_files = sorted(auction_dir.glob("*_solution_verification.json"))
    
    if not verification_files:
        print("No verification files found!")
        return
    
    print(f"Analyzing {len(verification_files)} verification files...\n")
    
    stats = {
        "total_files": len(verification_files),
        "total_solutions": 0,
        "total_swaps": 0,
        "swaps_with_errors": 0,
        "swaps_with_difference": 0,
        "error_files": 0,
    }
    
    error_types = defaultdict(int)
    pool_versions = defaultdict(int)  # V2 vs V3
    pool_types = defaultdict(int)     # Weighted, Stable, Gyro, etc.
    difference_ranges = {
        "0 bps": 0,
        "1-10 bps": 0,
        "11-50 bps": 0,
        "51-100 bps": 0,
        ">100 bps": 0,
    }
    
    files_with_errors = []
    swaps_with_large_differences = []
    error_details = []
    
    # Build a mapping of pool_id to pool_kind from liquidity files
    pool_id_to_kind = {}
    for verification_file in verification_files:
        auction_id = verification_file.stem.replace("_solution_verification", "")
        liquidity_file = auction_dir / f"{auction_id}_liquidity.json"
        
        if liquidity_file.exists():
            try:
                with open(liquidity_file, 'r') as f:
                    liq_data = json.load(f)
                    for pool in liq_data.get('liquidity', []):
                        pool_id_to_kind[pool.get('id')] = pool.get('kind', 'unknown')
            except Exception:
                pass  # Skip if we can't read the liquidity file
    
    for verification_file in verification_files:
        try:
            with open(verification_file, 'r') as f:
                data = json.load(f)
            
            auction_id = verification_file.stem.replace("_solution_verification", "")
            
            if not isinstance(data, list):
                print(f"Warning: {verification_file.name} is not a list")
                continue
            
            stats["total_solutions"] += len(data)
            
            for solution in data:
                solution_index = solution.get("solution_index", "?")
                swaps = solution.get("swaps", [])
                stats["total_swaps"] += len(swaps)
                
                for swap in swaps:
                    difference_bps = swap.get("difference_bps", 0)
                    quote_error = swap.get("quote_error")
                    
                    # Track pool version (V2 vs V3)
                    pool_version = swap.get("pool_version", "Unknown")
                    pool_versions[pool_version] += 1
                    
                    # Get pool kind from the liquidity mapping
                    pool_id = swap.get("pool_id", "?")
                    pool_kind = pool_id_to_kind.get(pool_id, "unknown")
                    
                    # Track pool types with version prefix
                    pool_type_key = f"{pool_version} {pool_kind}"
                    pool_types[pool_type_key] += 1
                    
                    # Track quote errors
                    if quote_error:
                        stats["swaps_with_errors"] += 1
                        error_types[quote_error] += 1
                        error_details.append({
                            "file": verification_file.name,
                            "auction_id": auction_id,
                            "solution_index": solution_index,
                            "interaction_index": swap.get("interaction_index", "?"),
                            "pool_id": swap.get("pool_id", "?"),
                            "token_in": swap.get("token_in", "?"),
                            "token_out": swap.get("token_out", "?"),
                            "error": quote_error
                        })
                    
                    # Track differences
                    if difference_bps is not None:
                        if difference_bps != 0:
                            stats["swaps_with_difference"] += 1
                        
                        if difference_bps == 0:
                            difference_ranges["0 bps"] += 1
                        elif difference_bps <= 10:
                            difference_ranges["1-10 bps"] += 1
                        elif difference_bps <= 50:
                            difference_ranges["11-50 bps"] += 1
                        elif difference_bps <= 100:
                            difference_ranges["51-100 bps"] += 1
                        else:
                            difference_ranges[">100 bps"] += 1
                            swaps_with_large_differences.append({
                                "file": verification_file.name,
                                "auction_id": auction_id,
                                "solution_index": solution_index,
                                "interaction_index": swap.get("interaction_index", "?"),
                                "pool_id": swap.get("pool_id", "?"),
                                "difference_bps": difference_bps,
                                "expected": swap.get("expected_amount_out"),
                                "quoted": swap.get("quoted_amount_out"),
                            })
                
        except Exception as e:
            stats["error_files"] += 1
            files_with_errors.append((verification_file.name, str(e)))
    
    # Print summary
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Total verification files:    {stats['total_files']}")
    print(f"Total solutions verified:    {stats['total_solutions']}")
    print(f"Total swaps verified:        {stats['total_swaps']}")
    print(f"Swaps with quote errors:     {stats['swaps_with_errors']} ({stats['swaps_with_errors']/max(stats['total_swaps'], 1)*100:.2f}%)")
    print(f"Swaps with differences:      {stats['swaps_with_difference']} ({stats['swaps_with_difference']/max(stats['total_swaps'], 1)*100:.2f}%)")
    print(f"Files with read errors:      {stats['error_files']}")
    print("=" * 80)
    
    # Print pool version breakdown
    if pool_versions:
        print("\nPOOL VERSION BREAKDOWN:")
        print("-" * 80)
        for version, count in sorted(pool_versions.items()):
            percentage = count / max(stats['total_swaps'], 1) * 100
            bar = "█" * int(percentage / 2)
            print(f"{version:>10}: {count:6} ({percentage:6.2f}%) {bar}")
        print("-" * 80)
    
    # Print pool type breakdown
    if pool_types:
        print("\nPOOL TYPE BREAKDOWN:")
        print("-" * 80)
        for pool_type, count in sorted(pool_types.items(), key=lambda x: x[1], reverse=True):
            percentage = count / max(stats['total_swaps'], 1) * 100
            bar = "█" * int(percentage / 2)
            print(f"{pool_type:>20}: {count:6} ({percentage:6.2f}%) {bar}")
        print("-" * 80)
    
    # Print difference distribution
    print("\nDIFFERENCE DISTRIBUTION (Expected vs Quoted):")
    print("-" * 80)
    for range_name, count in difference_ranges.items():
        percentage = count / max(stats['total_swaps'], 1) * 100
        bar = "█" * int(percentage / 2)
        print(f"{range_name:>12}: {count:6} ({percentage:6.2f}%) {bar}")
    print("-" * 80)
    
    # Print error types
    if error_types:
        print("\nERROR TYPES:")
        print("-" * 80)
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"{error_type}: {count}")
        print("-" * 80)
    
    # Print detailed errors
    if error_details:
        print(f"\n⚠ SWAPS WITH QUOTE ERRORS ({len(error_details)}):")
        print("-" * 80)
        for detail in error_details[:20]:  # Show first 20
            print(f"File: {detail['file']}")
            print(f"  Solution {detail['solution_index']}, Interaction {detail['interaction_index']}")
            print(f"  Pool: {detail['pool_id']}")
            print(f"  {detail['token_in'][:10]}... -> {detail['token_out'][:10]}...")
            print(f"  Error: {detail['error']}")
            print()
        if len(error_details) > 20:
            print(f"  ... and {len(error_details) - 20} more errors")
    else:
        print("\n✓ NO QUOTE ERRORS FOUND!")
    
    # Print large differences
    if swaps_with_large_differences:
        print(f"\n⚠ SWAPS WITH LARGE DIFFERENCES (>100 bps) ({len(swaps_with_large_differences)}):")
        print("-" * 80)
        for detail in swaps_with_large_differences[:10]:  # Show first 10
            print(f"File: {detail['file']}, Solution {detail['solution_index']}")
            print(f"  Pool: {detail['pool_id']}, Difference: {detail['difference_bps']} bps")
            print(f"  Expected: {detail['expected']}, Quoted: {detail['quoted']}")
            print()
        if len(swaps_with_large_differences) > 10:
            print(f"  ... and {len(swaps_with_large_differences) - 10} more large differences")
    else:
        print("\n✓ NO SWAPS WITH LARGE DIFFERENCES (>100 bps)!")
    
    # Print file errors
    if files_with_errors:
        print(f"\n⚠ FILES WITH READ ERRORS ({len(files_with_errors)}):")
        print("-" * 80)
        for filename, error in files_with_errors:
            print(f"  - {filename}: {error}")
    
    # Final assessment
    print("\n" + "=" * 80)
    print("OVERALL ASSESSMENT:")
    print("=" * 80)
    
    if stats['swaps_with_errors'] == 0 and stats['error_files'] == 0:
        print("✓ ALL VERIFICATIONS PASSED - No quote errors detected!")
    else:
        print("✗ ISSUES FOUND - See details above")
    
    accuracy_rate = (stats['total_swaps'] - stats['swaps_with_errors']) / max(stats['total_swaps'], 1) * 100
    print(f"Accuracy Rate: {accuracy_rate:.2f}%")
    
    perfect_match_rate = difference_ranges["0 bps"] / max(stats['total_swaps'], 1) * 100
    print(f"Perfect Match Rate (0 bps): {perfect_match_rate:.2f}%")
    print("=" * 80)
    
    return stats

if __name__ == "__main__":
    check_verifications()

