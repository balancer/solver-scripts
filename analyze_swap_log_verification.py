#!/usr/bin/env python3
"""
Comprehensive Swap Log Verification Analysis Script

Analyzes swap log verification files and generates a detailed markdown report
including success rates, error types, and difference distributions by pool type.

USAGE:
    python3 analyze_swap_log_verification.py

REQUIREMENTS:
    - Python 3.6+
    - Swap log verification JSON files in: auction-data/mainnet/
    - Files should match pattern: *_swap_log_verification.json

OUTPUT:
    - Generates: swap_log_verification_report.md
    - Contains comprehensive analysis including:
        * Overall success/error rates
        * Per-pool-type statistics
        * Error categorization and examples
        * Difference distribution percentiles
        * Detailed debugging information

EXAMPLE:
    $ python3 analyze_swap_log_verification.py
    Analyzing 3 verification files...
    Analysis complete. Processed 98,509 total swaps.
    Report written to: swap_log_verification_report.md
    ✅ Analysis complete!
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Any


class SwapLogAnalyzer:
    """Analyzes swap log verification data and generates reports."""
    
    def __init__(self, auction_dir: Path):
        self.auction_dir = auction_dir
        self.verification_files = sorted(auction_dir.glob("*_swap_log_verification.json"))
        
        # Statistics storage - keyed by "pool_type version" (e.g., "weightedProduct V2")
        self.pool_stats = defaultdict(lambda: {
            'total': 0,
            'verified': 0,
            'perfect': 0,
            'errors': 0,
            'within_1bps': 0,
            'within_10bps': 0,
            'within_100bps': 0,
            'over_100bps': 0,
            'pool_type': '',  # Store the base pool type
            'version': '',    # Store the version
        })
        
        self.available_liquidity = defaultdict(int)
        self.liquidity_files_processed = 0
        
        self.error_types = defaultdict(lambda: defaultdict(int))
        self.error_examples = defaultdict(list)
        self.difference_distributions = defaultdict(list)
        
        # Overall stats
        self.total_swaps = 0
        self.total_verified = 0
        self.total_errors = 0
        self.zero_amount_errors = 0
        self.vm_errors = 0
        self.other_errors = 0
        
        # Version-level aggregation stats
        self.v2_stats = {
            'total': 0,
            'verified': 0,
            'perfect': 0,
            'errors': 0,
        }
        self.v3_stats = {
            'total': 0,
            'verified': 0,
            'perfect': 0,
            'errors': 0,
        }
        
    def analyze(self):
        """Run the complete analysis on all verification files."""
        print(f"Analyzing {len(self.verification_files)} verification files...")
        
        for vf in self.verification_files:
            self._analyze_file(vf)
        
        print(f"Analysis complete. Processed {self.total_swaps} total swaps.")
    
    def _analyze_file(self, verification_file: Path):
        """Analyze a single verification file."""
        # First, try to analyze corresponding liquidity file
        try:
            liquidity_file = verification_file.parent / verification_file.name.replace('_swap_log_verification.json', '_liquidity.json')
            if liquidity_file.exists():
                self._analyze_liquidity(liquidity_file)
        except Exception as e:
            print(f"Error checking liquidity file for {verification_file.name}: {e}")

        try:
            with open(verification_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {verification_file}: {e}")
            return
        
        swaps = data.get('swaps', [])
        self.total_swaps += len(swaps)
        
        for swap in swaps:
            self._analyze_swap(swap, verification_file.name)
    
    def _analyze_liquidity(self, liquidity_file: Path):
        """Analyze a liquidity file to count available pools."""
        try:
            with open(liquidity_file, 'r') as f:
                data = json.load(f)
                
            self.liquidity_files_processed += 1
            liquidity = data.get('liquidity', [])
            for pool in liquidity:
                kind = pool.get('kind', 'Unknown')
                self.available_liquidity[kind] += 1
        except Exception as e:
            print(f"Error reading liquidity {liquidity_file}: {e}")

    def _analyze_swap(self, swap: Dict[str, Any], filename: str):
        """Analyze a single swap record."""
        pool_type = swap.get('kind', 'unknown')
        pool_version = swap.get('pool_version', 'Unknown')
        verified = swap.get('verified', False)
        diff_bps = swap.get('difference_bps')
        error = swap.get('error', '')
        amount_in = swap.get('amount_in', '0')
        
        # Create a combined key for pool type + version
        pool_key = f"{pool_type} {pool_version}"
        
        # Update pool type stats
        stats = self.pool_stats[pool_key]
        stats['total'] += 1
        stats['pool_type'] = pool_type
        stats['version'] = pool_version
        
        # Update version-level stats
        if pool_version == 'V2':
            self.v2_stats['total'] += 1
            if verified:
                self.v2_stats['verified'] += 1
            else:
                self.v2_stats['errors'] += 1
        elif pool_version == 'V3':
            self.v3_stats['total'] += 1
            if verified:
                self.v3_stats['verified'] += 1
            else:
                self.v3_stats['errors'] += 1
        
        if verified:
            self.total_verified += 1
            stats['verified'] += 1
            
            # Track difference distribution
            if diff_bps is not None:
                abs_diff = abs(diff_bps)
                self.difference_distributions[pool_key].append(abs_diff)
                
                if abs_diff == 0:
                    stats['perfect'] += 1
                    if pool_version == 'V2':
                        self.v2_stats['perfect'] += 1
                    elif pool_version == 'V3':
                        self.v3_stats['perfect'] += 1
                elif abs_diff <= 1:
                    stats['within_1bps'] += 1
                elif abs_diff <= 10:
                    stats['within_10bps'] += 1
                elif abs_diff <= 100:
                    stats['within_100bps'] += 1
                else:
                    stats['over_100bps'] += 1
        else:
            self.total_errors += 1
            stats['errors'] += 1
            
            # Categorize errors
            if amount_in == '0':
                self.zero_amount_errors += 1
                error_category = "Zero-amount swap"
            elif 'VM execution error' in error:
                self.vm_errors += 1
                error_category = "VM execution error"
            elif 'negative output delta' in error:
                self.other_errors += 1
                error_category = "Negative output delta"
            elif 'Swap failed in solver' in error:
                self.other_errors += 1
                error_category = "Solver calculation failed"
            else:
                self.other_errors += 1
                error_category = "Other error"
            
            # Track error types by pool type+version
            self.error_types[pool_key][error_category] += 1
            
            # Store example (limit to 3 per pool type+version per error category)
            key = f"{pool_key}_{error_category}"
            if len(self.error_examples.get(key, [])) < 3:
                if key not in self.error_examples:
                    self.error_examples[key] = []
                self.error_examples[key].append({
                    'filename': filename,
                    'pool_address': swap.get('pool_address', 'N/A'),
                    'pool_version': pool_version,
                    'token_in': swap.get('token_in', 'N/A'),
                    'token_out': swap.get('token_out', 'N/A'),
                    'amount_in': amount_in,
                    'expected_out': swap.get('expected_amount_out', 'N/A'),
                    'quoted_out': swap.get('quoted_amount_out', 'N/A'),
                    'error': error[:200] if error else 'N/A'
                })
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate percentile statistics for a list of values."""
        if not values:
            return {'p50': 0, 'p95': 0, 'p99': 0, 'max': 0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            'p50': sorted_values[int(n * 0.50)] if n > 0 else 0,
            'p95': sorted_values[int(n * 0.95)] if n > 0 else 0,
            'p99': sorted_values[int(n * 0.99)] if n > 0 else 0,
            'max': sorted_values[-1] if n > 0 else 0,
        }
    
    def generate_markdown_report(self, output_file: Path):
        """Generate a comprehensive markdown report."""
        report = []
        
        # Header
        report.append("# Swap Log Verification Analysis Report")
        report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**Verification Files Analyzed:** {len(self.verification_files)}")
        report.append("\n---\n")
        
        # Executive Summary
        report.append("## Executive Summary\n")
        report.append(f"- **Total Swaps Analyzed:** {self.total_swaps:,}")
        report.append(f"- **Liquidity Files Processed:** {self.liquidity_files_processed}")
        report.append(f"- **Successfully Verified:** {self.total_verified:,} ({self.total_verified/self.total_swaps*100:.1f}%)")
        report.append(f"- **Failed Verification:** {self.total_errors:,} ({self.total_errors/self.total_swaps*100:.1f}%)")
        
        perfect_count = sum(stats['perfect'] for stats in self.pool_stats.values())
        report.append(f"- **Perfect Matches (0 bps):** {perfect_count:,} ({perfect_count/self.total_swaps*100:.1f}%)")
        
        # Version breakdown
        report.append("\n### Balancer Version Breakdown\n")
        v2_total = self.v2_stats['total']
        v2_verified = self.v2_stats['verified']
        v2_perfect = self.v2_stats['perfect']
        v2_errors = self.v2_stats['errors']
        
        v3_total = self.v3_stats['total']
        v3_verified = self.v3_stats['verified']
        v3_perfect = self.v3_stats['perfect']
        v3_errors = self.v3_stats['errors']
        
        report.append("| Version | Total Swaps | Success Rate | Perfect Match Rate | Error Rate |")
        report.append("|---------|------------:|-------------:|-------------------:|-----------:|")
        if v2_total > 0:
            report.append(f"| **Balancer V2** | {v2_total:,} | {v2_verified/v2_total*100:.1f}% | {v2_perfect/v2_total*100:.1f}% | {v2_errors/v2_total*100:.1f}% |")
        if v3_total > 0:
            report.append(f"| **Balancer V3** | {v3_total:,} | {v3_verified/v3_total*100:.1f}% | {v3_perfect/v3_total*100:.1f}% | {v3_errors/v3_total*100:.1f}% |")
        
        report.append("\n---\n")
        
        # Liquidity Availability
        report.append("## Liquidity Availability vs Usage\n")
        report.append("This table compares the number of pools available in the auction data vs the number of swaps executed against them.\n")
        report.append("\n| Pool Type | Available Count | Used in Swaps | Utilization (Swaps/Available) |")
        report.append("|-----------|----------------:|--------------:|------------------------------:|")
        
        # Aggregate used stats by pool type (ignoring version for this table)
        used_by_type = defaultdict(int)
        for stats in self.pool_stats.values():
            used_by_type[stats['pool_type']] += stats['total']
            
        # Merge keys from both
        all_types = sorted(set(self.available_liquidity.keys()) | set(used_by_type.keys()))
        
        for pool_type in all_types:
            available = self.available_liquidity.get(pool_type, 0)
            used = used_by_type.get(pool_type, 0)
            ratio = (used / available) if available > 0 else 0
            
            report.append(f"| {pool_type} | {available:,} | {used:,} | {ratio:.2f} |")
            
        report.append("\n> **Note:** 'Available Count' sums the number of pools of this type across all auction files. 'Used in Swaps' counts total swaps.\n")
        report.append("\n---\n")

        # Error Breakdown
        report.append("## Error Analysis\n")
        report.append("### Error Categories\n")
        report.append(f"| Category | Count | Percentage |")
        report.append(f"|----------|------:|----------:|")
        report.append(f"| Zero-amount swaps | {self.zero_amount_errors:,} | {self.zero_amount_errors/self.total_errors*100:.1f}% |")
        report.append(f"| VM execution errors | {self.vm_errors:,} | {self.vm_errors/self.total_errors*100:.1f}% |")
        report.append(f"| Other errors | {self.other_errors:,} | {self.other_errors/self.total_errors*100:.1f}% |")
        report.append(f"| **Total Errors** | **{self.total_errors:,}** | **100.0%** |")
        report.append("\n> **Note:** Zero-amount swaps are edge cases and may not indicate actual calculation errors.\n")
        report.append("\n---\n")
        
        # Pool Type Comparison Table
        report.append("## Pool Type Summary\n")
        report.append("\n| Pool Type | Balancer Version | Total | Success Rate | Perfect Match | Median Diff | P99 Diff | Max Diff |")
        report.append("|-----------|------------------|------:|--------------:|--------------:|------------:|---------:|---------:|")
        
        # Sort for the summary table: first by version (V2 before V3), then by pool_type
        sorted_for_summary = sorted(
            self.pool_stats.items(),
            key=lambda x: (x[1]['version'], x[1]['pool_type'])
        )
        
        for pool_key, stats in sorted_for_summary:
            total = stats['total']
            verified = stats['verified']
            perfect = stats['perfect']
            pool_type = stats['pool_type']
            version = stats['version']
            
            success_rate = (verified / total * 100) if total > 0 else 0
            perfect_rate = (perfect / total * 100) if total > 0 else 0
            
            # Get percentiles
            if pool_key in self.difference_distributions and self.difference_distributions[pool_key]:
                percentiles = self._calculate_percentiles(self.difference_distributions[pool_key])
                median = percentiles['p50']
                p99 = percentiles['p99']
                max_diff = percentiles['max']
            else:
                median = 0
                p99 = 0
                max_diff = 0
            
            report.append(f"| {pool_type} | {version} | {total:,} | {success_rate:.1f}% | {perfect_rate:.1f}% | {median:.2f} | {p99:.2f} | {max_diff:.2f} |")
        
        report.append("\n> **Note:** All differences shown in basis points (bps). 1 bps = 0.01%\n")
        report.append("\n---\n")
        
        # V2 vs V3 Comparison for pool types that exist in both
        report.append("## Balancer V2 vs V3 Comparison\n")
        report.append("\nThis section compares pool types that exist in both Balancer V2 and V3.\n")
        
        # Group by pool type
        pools_by_type = defaultdict(dict)
        for pool_key, stats in self.pool_stats.items():
            pool_type = stats['pool_type']
            version = stats['version']
            pools_by_type[pool_type][version] = stats
        
        # Find pool types with both V2 and V3
        comparison_types = []
        for pool_type, versions in pools_by_type.items():
            if 'V2' in versions and 'V3' in versions:
                comparison_types.append(pool_type)
        
        if comparison_types:
            report.append("\n| Pool Type | Metric | Balancer V2 | Balancer V3 | Difference |")
            report.append("|-----------|--------|-------------|-------------|------------|")
            
            for pool_type in sorted(comparison_types):
                v2_stats = pools_by_type[pool_type]['V2']
                v3_stats = pools_by_type[pool_type]['V3']
                
                v2_total = v2_stats['total']
                v3_total = v3_stats['total']
                v2_success_rate = (v2_stats['verified'] / v2_total * 100) if v2_total > 0 else 0
                v3_success_rate = (v3_stats['verified'] / v3_total * 100) if v3_total > 0 else 0
                v2_perfect_rate = (v2_stats['perfect'] / v2_total * 100) if v2_total > 0 else 0
                v3_perfect_rate = (v3_stats['perfect'] / v3_total * 100) if v3_total > 0 else 0
                
                report.append(f"| {pool_type} | **Total Swaps** | {v2_total:,} | {v3_total:,} | - |")
                report.append(f"| {pool_type} | **Success Rate** | {v2_success_rate:.1f}% | {v3_success_rate:.1f}% | {v2_success_rate - v3_success_rate:+.1f}% |")
                report.append(f"| {pool_type} | **Perfect Match Rate** | {v2_perfect_rate:.1f}% | {v3_perfect_rate:.1f}% | {v2_perfect_rate - v3_perfect_rate:+.1f}% |")
                
                # Get difference percentiles for comparison
                v2_key = f"{pool_type} V2"
                v3_key = f"{pool_type} V3"
                if v2_key in self.difference_distributions and v3_key in self.difference_distributions:
                    v2_p99 = self._calculate_percentiles(self.difference_distributions[v2_key])['p99']
                    v3_p99 = self._calculate_percentiles(self.difference_distributions[v3_key])['p99']
                    report.append(f"| {pool_type} | **P99 Difference (bps)** | {v2_p99:.2f} | {v3_p99:.2f} | {v2_p99 - v3_p99:+.2f} |")
                
                report.append("| | | | | |")  # Separator row
        else:
            report.append("\n*No pool types found in both V2 and V3.*\n")
        
        report.append("\n---\n")
        
        # Pool Type Analysis
        report.append("## Detailed Pool Type Analysis\n")
        
        # Sort pool types: first by version (V2 before V3), then by pool_type alphabetically
        sorted_pool_types = sorted(
            self.pool_stats.items(),
            key=lambda x: (x[1]['version'], x[1]['pool_type'])
        )
        
        # Add section headers for V2 and V3 and generate sections
        current_version = None
        for pool_key, stats in sorted_pool_types:
            version = stats['version']
            if version != current_version:
                if current_version is not None:
                    report.append("")  # Add spacing between version sections
                report.append(f"### Balancer {version} Pools\n")
                current_version = version
            
            report.extend(self._generate_pool_type_section(pool_key, stats))
        
        # Detailed Error Examples
        report.append("\n---\n")
        report.append("## Detailed Error Examples\n")
        report.append("\n> Examples of failed verifications for debugging purposes.\n")
        
        # Group error examples by version
        current_version = None
        for pool_key, stats in sorted_pool_types:
            if stats['errors'] > 0:
                version = stats['version']
                if version != current_version:
                    if current_version is not None:
                        report.append("")  # Add spacing between version sections
                    report.append(f"### Balancer {version} Error Examples\n")
                    current_version = version
                report.extend(self._generate_error_examples_section(pool_key, stats))
        
        # Footer
        report.append("\n---\n")
        report.append("## Methodology\n")
        report.append("\n")
        report.append("This report analyzes swap log verification data by:\n")
        report.append("1. Comparing solver-calculated outputs against on-chain contract quotes\n")
        report.append("2. Calculating basis point (bps) differences between expected and quoted amounts\n")
        report.append("3. Categorizing swaps by pool type and version (V2/V3)\n")
        report.append("4. Analyzing error patterns and edge cases\n")
        report.append("\n")
        report.append("**Perfect Match**: 0 bps difference (exact match)\n")
        report.append("**Within N bps**: Absolute difference ≤ N basis points\n")
        report.append("**1 bps** = 0.01% difference\n")
        
        # Write report
        with open(output_file, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"\nReport written to: {output_file}")
    
    def _generate_pool_type_section(self, pool_key: str, stats: Dict[str, int]) -> List[str]:
        """Generate markdown section for a pool type+version combination."""
        section = []
        
        total = stats['total']
        verified = stats['verified']
        perfect = stats['perfect']
        errors = stats['errors']
        pool_type = stats['pool_type']
        version = stats['version']
        
        # Calculate rates
        success_rate = (verified / total * 100) if total > 0 else 0
        perfect_rate = (perfect / total * 100) if total > 0 else 0
        error_rate = (errors / total * 100) if total > 0 else 0
        
        # Determine status emoji
        if perfect_rate >= 99:
            status = "✅ PERFECT"
        elif success_rate >= 95:
            status = "✅ EXCELLENT"
        elif success_rate >= 85:
            status = "✅ GOOD"
        elif success_rate >= 70:
            status = "⚠️ MODERATE"
        else:
            status = "❌ PROBLEMATIC"
        
        section.append(f"#### {pool_type} ({version}) {status}\n")
        
        # Summary table
        section.append("| Metric | Count | Percentage |")
        section.append("|--------|------:|-----------:|")
        section.append(f"| Total Swaps | {total:,} | 100.0% |")
        section.append(f"| Successfully Verified | {verified:,} | {success_rate:.1f}% |")
        section.append(f"| Failed Verification | {errors:,} | {error_rate:.1f}% |")
        section.append(f"| Perfect Matches (0 bps) | {perfect:,} | {perfect_rate:.1f}% |")
        
        # Difference distribution for verified swaps
        if verified > 0:
            within_1bps = stats['within_1bps']
            within_10bps = stats['within_10bps']
            within_100bps = stats['within_100bps']
            over_100bps = stats['over_100bps']
            
            section.append(f"| Within 1 bps | {within_1bps:,} | {within_1bps/total*100:.1f}% |")
            section.append(f"| Within 2-10 bps | {within_10bps:,} | {within_10bps/total*100:.1f}% |")
            section.append(f"| Within 11-100 bps | {within_100bps:,} | {within_100bps/total*100:.1f}% |")
            section.append(f"| Over 100 bps | {over_100bps:,} | {over_100bps/total*100:.1f}% |")
        
        # Percentile statistics for differences
        if pool_key in self.difference_distributions and self.difference_distributions[pool_key]:
            percentiles = self._calculate_percentiles(self.difference_distributions[pool_key])
            section.append("\n**Difference Distribution (for verified swaps):**")
            section.append(f"- Median (p50): {percentiles['p50']:.2f} bps")
            section.append(f"- 95th percentile: {percentiles['p95']:.2f} bps")
            section.append(f"- 99th percentile: {percentiles['p99']:.2f} bps")
            section.append(f"- Maximum: {percentiles['max']:.2f} bps")
        
        # Error type breakdown
        if errors > 0:
            section.append("\n**Error Breakdown:**")
            error_types = self.error_types[pool_key]
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                section.append(f"- {error_type}: {count:,} ({count/errors*100:.1f}% of errors)")
        
        section.append("\n")
        return section
    
    def _generate_error_examples_section(self, pool_key: str, stats: Dict[str, Any]) -> List[str]:
        """Generate error examples section for a pool type+version."""
        section = []
        
        error_types = self.error_types[pool_key]
        if not error_types:
            return section
        
        pool_type = stats.get('pool_type', 'Unknown')
        version = stats.get('version', 'Unknown')
        section.append(f"#### {pool_type} ({version}) - Error Examples\n")
        
        for error_category in sorted(error_types.keys()):
            key = f"{pool_key}_{error_category}"
            examples = self.error_examples.get(key, [])
            
            if examples:
                section.append(f"#### {error_category}\n")
                
                for i, example in enumerate(examples, 1):
                    section.append(f"**Example {i}:**")
                    section.append(f"- File: `{example['filename']}`")
                    section.append(f"- Pool: `{example['pool_address']}`")
                    section.append(f"- Version: {example['pool_version']}")
                    section.append(f"- Token In: `{example['token_in']}`")
                    section.append(f"- Token Out: `{example['token_out']}`")
                    section.append(f"- Amount In: `{example['amount_in']}`")
                    section.append(f"- Expected Out: `{example['expected_out']}`")
                    if example['quoted_out'] != 'N/A':
                        section.append(f"- Quoted Out: `{example['quoted_out']}`")
                    section.append(f"- Error: `{example['error']}`")
                    section.append("")
        
        return section


def main():
    """Main entry point for the script."""
    # Configuration
    auction_dir = Path("auction-data/mainnet")
    timestamp = int(datetime.now().timestamp())
    output_file = Path(f"swap_log_verification_report_{timestamp}.md")
    
    # Check if auction directory exists
    if not auction_dir.exists():
        print(f"Error: Directory {auction_dir} does not exist")
        return 1
    
    # Create analyzer and run analysis
    analyzer = SwapLogAnalyzer(auction_dir)
    analyzer.analyze()
    
    # Generate report
    analyzer.generate_markdown_report(output_file)
    
    print("\n✅ Analysis complete!")
    print(f"\n📊 Summary:")
    print(f"   Total swaps: {analyzer.total_swaps:,}")
    print(f"   Success rate: {analyzer.total_verified/analyzer.total_swaps*100:.1f}%")
    print(f"   Error rate: {analyzer.total_errors/analyzer.total_swaps*100:.1f}%")
    
    return 0


if __name__ == "__main__":
    exit(main())

