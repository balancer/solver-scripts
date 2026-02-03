#!/usr/bin/env python3
"""
Script to check if all solution files in auction-data are empty.
"""

import json
import os
from pathlib import Path
from collections import defaultdict

def check_solutions():
    auction_dir = Path("auction-data/mainnet")
    
    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return
    
    # Find all solution files
    solution_files = sorted(auction_dir.glob("*_solutions.json"))
    
    if not solution_files:
        print("No solution files found!")
        return
    
    print(f"Checking {len(solution_files)} solution files...\n")
    
    stats = {
        "total": len(solution_files),
        "empty": 0,
        "with_solutions": 0,
        "error": 0
    }
    
    files_with_solutions = []
    files_with_errors = []
    
    for solution_file in solution_files:
        try:
            with open(solution_file, 'r') as f:
                data = json.load(f)
            
            solutions = data.get("solutions", [])
            
            if len(solutions) == 0:
                stats["empty"] += 1
            else:
                stats["with_solutions"] += 1
                files_with_solutions.append((solution_file.name, len(solutions)))
                
        except Exception as e:
            stats["error"] += 1
            files_with_errors.append((solution_file.name, str(e)))
    
    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total solution files:        {stats['total']}")
    print(f"Empty (no solutions):        {stats['empty']} ({stats['empty']/stats['total']*100:.1f}%)")
    print(f"With solutions:              {stats['with_solutions']} ({stats['with_solutions']/stats['total']*100:.1f}%)")
    print(f"Errors reading file:         {stats['error']}")
    print("=" * 70)
    
    if files_with_solutions:
        print(f"\n✓ Files with solutions ({len(files_with_solutions)}):")
        for filename, count in files_with_solutions[:10]:  # Show first 10
            print(f"  - {filename}: {count} solution(s)")
        if len(files_with_solutions) > 10:
            print(f"  ... and {len(files_with_solutions) - 10} more")
    else:
        print("\n✗ NO SOLUTIONS FOUND IN ANY FILE!")
    
    if files_with_errors:
        print(f"\n⚠ Files with errors ({len(files_with_errors)}):")
        for filename, error in files_with_errors[:5]:  # Show first 5
            print(f"  - {filename}: {error}")
    
    return stats

if __name__ == "__main__":
    check_solutions()









