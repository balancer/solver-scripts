#!/usr/bin/env python3
"""
Master script to run complete analysis pipeline on auction data.

This script:
1. Scans auction data directory for solutions
2. Filters out empty solutions
3. Generates detailed analysis JSON files
4. Runs verification checks
5. Produces summary reports
6. Saves results to timestamped output directory
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def print_header(title, width=100):
    """Print a nice header."""
    print("\n" + "=" * width)
    print(f"{title:^{width}}")
    print("=" * width)

def print_section(title, width=100):
    """Print a section divider."""
    print(f"\n{title}")
    print("-" * width)

def check_solutions(auction_dir):
    """Check which auction files have solutions."""
    print_header("STEP 1: SCANNING FOR SOLUTIONS")
    
    solution_files = sorted(auction_dir.glob("*_solutions.json"))
    
    stats = {
        'total': len(solution_files),
        'with_solutions': 0,
        'empty': 0,
        'errors': 0,
        'auction_ids': [],
        'empty_auction_ids': []
    }
    
    print(f"Scanning {stats['total']} solution files...")
    
    for solution_file in solution_files:
        # Skip enhanced solutions
        if 'enhanced' in solution_file.name:
            continue
            
        auction_id = solution_file.stem.replace('_solutions', '')
        
        try:
            with open(solution_file) as f:
                data = json.load(f)
                solutions = data.get('solutions', [])
                
                if solutions and len(solutions) > 0:
                    stats['with_solutions'] += 1
                    stats['auction_ids'].append(auction_id)
                else:
                    stats['empty'] += 1
                    stats['empty_auction_ids'].append(auction_id)
        except Exception as e:
            stats['errors'] += 1
            print(f"  ✗ Error reading {solution_file.name}: {e}")
    
    print_section("SOLUTION SCAN RESULTS")
    print(f"Total solution files:        {stats['total']:>6}")
    print(f"With solutions:              {stats['with_solutions']:>6} ({stats['with_solutions']/max(stats['total'],1)*100:.1f}%)")
    print(f"Empty (no solutions):        {stats['empty']:>6} ({stats['empty']/max(stats['total'],1)*100:.1f}%)")
    print(f"Errors reading file:         {stats['errors']:>6}")
    
    return stats

def cleanup_empty_auctions(auction_dir, empty_auction_ids):
    """Remove auction files that don't have solutions."""
    print_header("STEP 2: CLEANING UP EMPTY AUCTION FILES")
    
    if not empty_auction_ids:
        print("✓ No empty auction files to clean up")
        return 0
    
    print(f"Found {len(empty_auction_ids)} auctions without solutions")
    print("These files will be removed to save space...")
    
    # File patterns to remove for each auction
    file_patterns = [
        '_auction.json',
        '_competition.json',
        '_liquidity.json',
        '_solutions.json',
        '_enhanced_solutions.json',
        '_solution_verification.json',
        '_analysis.json'
    ]
    
    removed_count = 0
    total_size = 0
    
    for auction_id in empty_auction_ids:
        for pattern in file_patterns:
            file_path = auction_dir / f"{auction_id}{pattern}"
            if file_path.exists():
                try:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    removed_count += 1
                    total_size += size
                except Exception as e:
                    print(f"  ✗ Error removing {file_path.name}: {e}")
    
    # Convert size to human readable
    if total_size < 1024:
        size_str = f"{total_size} bytes"
    elif total_size < 1024 * 1024:
        size_str = f"{total_size / 1024:.1f} KB"
    else:
        size_str = f"{total_size / (1024 * 1024):.1f} MB"
    
    print_section("CLEANUP RESULTS")
    print(f"Files removed:               {removed_count:>6}")
    print(f"Space freed:                 {size_str:>12}")
    print(f"Auctions cleaned:            {len(empty_auction_ids):>6}")
    
    return removed_count

def check_required_files(auction_dir, auction_ids):
    """Check which auctions have all required files for analysis."""
    print_header("STEP 3: CHECKING REQUIRED FILES")
    
    required_suffixes = ['_auction.json', '_competition.json', '_liquidity.json', '_solutions.json']
    
    valid_auctions = []
    missing_files = defaultdict(list)
    
    for auction_id in auction_ids:
        has_all = True
        for suffix in required_suffixes:
            file_path = auction_dir / f"{auction_id}{suffix}"
            if not file_path.exists():
                has_all = False
                missing_files[auction_id].append(suffix)
        
        if has_all:
            valid_auctions.append(auction_id)
    
    print(f"\nAuctions with solutions:     {len(auction_ids)}")
    print(f"Auctions with all files:     {len(valid_auctions)}")
    print(f"Auctions missing files:      {len(auction_ids) - len(valid_auctions)}")
    
    if missing_files:
        print_section("MISSING FILES")
        for auction_id, missing in sorted(missing_files.items())[:10]:
            print(f"  Auction {auction_id}: missing {', '.join(missing)}")
        if len(missing_files) > 10:
            print(f"  ... and {len(missing_files) - 10} more")
    
    return valid_auctions

def generate_analysis(auction_dir, auction_ids):
    """Generate detailed analysis JSON files."""
    print_header("STEP 4: GENERATING DETAILED ANALYSIS")
    
    print(f"Generating analysis for {len(auction_ids)} auctions...")
    print("This may take a moment...\n")
    
    try:
        # Run the detailed comparison script (from the parent directory)
        script_dir = Path(__file__).parent
        result = subprocess.run(
            ['python3', str(script_dir / 'compare_solutions_detailed.py')],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"✗ Error running analysis script:")
            print(result.stderr)
            return False
        
        # Count generated files
        analysis_files = list(auction_dir.glob("*_analysis.json"))
        print(f"✓ Generated {len(analysis_files)} analysis files")
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ Analysis timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Error running analysis: {e}")
        return False

def run_verification(auction_dir):
    """Run solution verification checks."""
    print_header("STEP 5: RUNNING VERIFICATION CHECKS")
    
    print("Checking solution accuracy via on-chain verification...\n")
    
    try:
        script_dir = Path(__file__).parent
        result = subprocess.run(
            ['python3', str(script_dir / 'check_verification.py')],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Print the output
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"\n✗ Verification had issues:")
            print(result.stderr)
            return False
        
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ Verification timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Error running verification: {e}")
        return False

def generate_summary_report(auction_dir):
    """Generate summary statistics from analysis files."""
    print_header("STEP 6: GENERATING SUMMARY REPORT")
    
    analysis_files = list(auction_dir.glob("*_analysis.json"))
    
    if not analysis_files:
        print("✗ No analysis files found")
        return None
    
    stats = {
        'total_auctions': len(analysis_files),
        'valid_solutions': 0,
        'competitive': 0,
        'beat_winner': 0,
        'total_surplus': 0,
        'pool_types': defaultdict(int),
        'pool_versions': defaultdict(int),
        'pool_addresses': defaultdict(lambda: {'count': 0, 'wins': 0, 'type': '', 'version': '', 'fee': ''}),
        'wins': [],
        'losses': []
    }
    
    for analysis_file in analysis_files:
        try:
            with open(analysis_file) as f:
                data = json.load(f)
            
            auction_id = data['auction_id']
            is_win = data.get('beat_winner', False)
            
            # Load verification file to get pool versions
            verification_file = auction_dir / f"{auction_id}_solution_verification.json"
            pool_version_map = {}
            if verification_file.exists():
                try:
                    with open(verification_file) as vf:
                        verif_data = json.load(vf)
                        for solution in verif_data:
                            for swap in solution.get('swaps', []):
                                pool_id = swap.get('pool_id')
                                pool_version = swap.get('pool_version', 'Unknown')
                                if pool_id:
                                    pool_version_map[pool_id] = pool_version
                except:
                    pass
            
            if data.get('valid'):
                stats['valid_solutions'] += 1
            
            if data.get('competitive'):
                stats['competitive'] += 1
            
            if is_win:
                stats['beat_winner'] += 1
                stats['wins'].append({
                    'auction_id': auction_id,
                    'pool_type': list(data['pool_stats'].keys())[0] if data['pool_stats'] else 'unknown'
                })
            else:
                stats['losses'].append({
                    'auction_id': auction_id,
                    'pool_type': list(data['pool_stats'].keys())[0] if data['pool_stats'] else 'unknown'
                })
            
            # Pool statistics
            for pool_type, count in data.get('pool_stats', {}).items():
                stats['pool_types'][pool_type] += count
            
            # Extract pool information from interactions
            for interaction in data.get('interactions', []):
                pool_id = interaction.get('pool_id', '')
                pool_address = interaction.get('pool_address', '')
                pool_kind = interaction.get('pool_kind', '')
                pool_fee = interaction.get('pool_fee', '')
                pool_version = pool_version_map.get(pool_id, 'Unknown')
                
                if pool_address:
                    stats['pool_addresses'][pool_address]['count'] += 1
                    if is_win:
                        stats['pool_addresses'][pool_address]['wins'] += 1
                    stats['pool_addresses'][pool_address]['type'] = pool_kind
                    stats['pool_addresses'][pool_address]['version'] = pool_version
                    stats['pool_addresses'][pool_address]['fee'] = pool_fee
                
                # Track pool versions
                if pool_version != 'Unknown':
                    stats['pool_versions'][pool_version] += 1
            
            # Calculate surplus
            for trade in data.get('trades', []):
                stats['total_surplus'] += trade.get('surplus_vs_min_pct', 0)
        
        except Exception as e:
            print(f"  ✗ Error reading {analysis_file.name}: {e}")
    
    # Calculate averages
    avg_surplus = stats['total_surplus'] / max(stats['total_auctions'], 1)
    
    # Print summary
    print_section("PERFORMANCE SUMMARY")
    print(f"Total Auctions Analyzed:     {stats['total_auctions']:>6}")
    print(f"Valid Solutions:             {stats['valid_solutions']:>6} ({stats['valid_solutions']/max(stats['total_auctions'],1)*100:.1f}%)")
    print(f"Beat Winner:                 {stats['beat_winner']:>6} ({stats['beat_winner']/max(stats['total_auctions'],1)*100:.1f}%)")
    print(f"Average Surplus:             {avg_surplus:>6.2f}%")
    
    print_section("POOL VERSIONS")
    total_versions = sum(stats['pool_versions'].values())
    for version, count in sorted(stats['pool_versions'].items(), key=lambda x: -x[1]):
        pct = count / max(total_versions, 1) * 100
        print(f"  {version:<20} {count:>4} ({pct:>5.1f}%)")
    
    print_section("POOL TYPES")
    total_pool_usages = sum(stats['pool_types'].values())
    for pool_type, count in sorted(stats['pool_types'].items(), key=lambda x: -x[1]):
        pct = count / max(total_pool_usages, 1) * 100
        print(f"  {pool_type:<20} {count:>4} ({pct:>5.1f}%)")
    
    print_section("SPECIFIC POOLS USED")
    for pool_address, info in sorted(stats['pool_addresses'].items(), key=lambda x: -x[1]['count']):
        win_rate = (info['wins'] / info['count'] * 100) if info['count'] > 0 else 0
        print(f"  {pool_address}")
        print(f"    Version: {info['version']:<5}  Type: {info['type']:<20}  Fee: {info['fee']}")
        print(f"    Uses: {info['count']:>3}  Wins: {info['wins']:>3}  Win Rate: {win_rate:>5.1f}%")
    
    print_section("WINS")
    if stats['wins']:
        for win in stats['wins'][:10]:
            print(f"  ✓ Auction {win['auction_id']} ({win['pool_type']})")
        if len(stats['wins']) > 10:
            print(f"  ... and {len(stats['wins']) - 10} more")
    else:
        print("  No wins in this dataset")
    
    return stats

def save_report(stats, output_dir):
    """Save analysis report to JSON file."""
    print_header("STEP 7: SAVING REPORT")
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = output_dir / f"analysis_report_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # Save stats
    report_file = report_dir / "summary_report.json"
    with open(report_file, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    
    print(f"✓ Report saved to: {report_file}")
    
    # Create markdown report
    md_file = report_dir / "ANALYSIS_REPORT.md"
    with open(md_file, 'w') as f:
        f.write(f"# Solution Analysis Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total Auctions: {stats['total_auctions']}\n")
        f.write(f"- Valid Solutions: {stats['valid_solutions']} ({stats['valid_solutions']/max(stats['total_auctions'],1)*100:.1f}%)\n")
        f.write(f"- Win Rate: {stats['beat_winner']} / {stats['total_auctions']} ({stats['beat_winner']/max(stats['total_auctions'],1)*100:.1f}%)\n")
        f.write(f"- Average Surplus: {stats['total_surplus']/max(stats['total_auctions'],1):.2f}%\n\n")
        
        f.write(f"## Pool Versions\n\n")
        total_versions = sum(stats['pool_versions'].values())
        for version, count in sorted(stats['pool_versions'].items(), key=lambda x: -x[1]):
            pct = count / max(total_versions, 1) * 100
            f.write(f"- {version}: {count} ({pct:.1f}%)\n")
        
        f.write(f"\n## Pool Types\n\n")
        total_pool_usages = sum(stats['pool_types'].values())
        for pool_type, count in sorted(stats['pool_types'].items(), key=lambda x: -x[1]):
            pct = count / max(total_pool_usages, 1) * 100
            f.write(f"- {pool_type}: {count} ({pct:.1f}%)\n")
        
        f.write(f"\n## Specific Pools Used\n\n")
        for pool_address, info in sorted(stats['pool_addresses'].items(), key=lambda x: -x[1]['count']):
            win_rate = (info['wins'] / info['count'] * 100) if info['count'] > 0 else 0
            f.write(f"### Pool: `{pool_address}`\n\n")
            f.write(f"- **Version**: {info['version']}\n")
            f.write(f"- **Type**: {info['type']}\n")
            f.write(f"- **Fee**: {info['fee']}\n")
            f.write(f"- **Total Uses**: {info['count']}\n")
            f.write(f"- **Wins**: {info['wins']} ({win_rate:.1f}% win rate)\n\n")
        
        f.write(f"\n## Wins ({len(stats['wins'])})\n\n")
        for win in stats['wins']:
            f.write(f"- Auction {win['auction_id']} ({win['pool_type']})\n")
        
        f.write(f"\n## Losses ({len(stats['losses'])})\n\n")
        for loss in stats['losses']:
            f.write(f"- Auction {loss['auction_id']} ({loss['pool_type']})\n")
    
    print(f"✓ Markdown report saved to: {md_file}")
    
    return report_dir

def main():
    """Main execution function."""
    print_header("BALANCER SOLVER - COMPLETE ANALYSIS PIPELINE", 100)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Configuration
    auction_dir = Path("auction-data/mainnet")
    output_dir = Path("analysis_reports")
    output_dir.mkdir(exist_ok=True)
    
    if not auction_dir.exists():
        print(f"\n✗ Error: Auction directory not found: {auction_dir}")
        print("Please make sure auction data is in auction-data/mainnet/")
        return 1
    
    # Step 1: Scan for solutions
    solution_stats = check_solutions(auction_dir)
    
    # Step 2: Clean up empty auction files (always run, even if no solutions)
    cleanup_empty_auctions(auction_dir, solution_stats['empty_auction_ids'])
    
    if solution_stats['with_solutions'] == 0:
        print("\n✗ No solutions found in auction data!")
        print("But empty files were cleaned up. ✓")
        return 0  # Exit successfully after cleanup
    
    # Step 3: Check required files
    valid_auctions = check_required_files(auction_dir, solution_stats['auction_ids'])
    
    if not valid_auctions:
        print("\n✗ No auctions have all required files!")
        print("Each auction needs: _auction.json, _competition.json, _liquidity.json, _solutions.json")
        return 1
    
    print(f"\n✓ Found {len(valid_auctions)} auctions ready for analysis")
    
    # Step 4: Generate analysis
    if not generate_analysis(auction_dir, valid_auctions):
        print("\n✗ Failed to generate analysis")
        return 1
    
    # Step 5: Run verification (optional, can fail without stopping)
    print("\n" + "=" * 100)
    run_verification(auction_dir)
    
    # Step 6: Generate summary
    stats = generate_summary_report(auction_dir)
    
    if not stats:
        print("\n✗ Failed to generate summary report")
        return 1
    
    # Step 7: Save report
    report_dir = save_report(stats, output_dir)
    
    # Final summary
    print_header("ANALYSIS COMPLETE", 100)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n✓ Analyzed {stats['total_auctions']} auctions")
    print(f"✓ Win rate: {stats['beat_winner']}/{stats['total_auctions']} ({stats['beat_winner']/max(stats['total_auctions'],1)*100:.1f}%)")
    print(f"✓ Reports saved to: {report_dir}")
    
    print("\n💡 Next steps:")
    print(f"   1. View summary: python3 view_analysis.py summary")
    print(f"   2. View details: python3 view_analysis.py list")
    print(f"   3. Check pools:  python3 view_analysis.py pools")
    print(f"   4. Read report:  cat {report_dir / 'ANALYSIS_REPORT.md'}")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n✗ Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

