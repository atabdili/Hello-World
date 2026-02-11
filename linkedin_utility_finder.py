#!/usr/bin/env python3
"""
LinkedIn Utility Finder — CSV Mode

Scans your LinkedIn connections export (CSV) to find people who work at
utility companies (electric, gas, water, etc.).

Usage:
    1. Export your LinkedIn connections:
       LinkedIn > Settings > Data Privacy > Get a copy of your data > Connections
    2. Download the CSV file when LinkedIn emails it to you
    3. Run: python linkedin_utility_finder.py Connections.csv
"""

import argparse
import csv
import sys
from pathlib import Path

from utility_matcher import is_utility_company


def detect_csv_columns(headers):
    """Detect which columns contain the relevant data."""
    col_map = {
        "first_name": None,
        "last_name": None,
        "company": None,
        "position": None,
    }

    first_name_candidates = ["first name", "first_name", "firstname"]
    last_name_candidates = ["last name", "last_name", "lastname"]
    company_candidates = ["company", "organization", "employer"]
    position_candidates = ["position", "title", "job title", "job_title", "role"]

    for i, h in enumerate(h.strip().lower() for h in headers):
        if h in first_name_candidates:
            col_map["first_name"] = i
        elif h in last_name_candidates:
            col_map["last_name"] = i
        elif h in company_candidates:
            col_map["company"] = i
        elif h in position_candidates:
            col_map["position"] = i

    return col_map


def parse_connections_csv(filepath):
    """Parse a LinkedIn connections CSV and return rows as dicts."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    connections = []

    with open(path, newline="", encoding="utf-8-sig") as f:
        raw_lines = f.readlines()

    header_idx = None
    for i, line in enumerate(raw_lines):
        lower = line.lower()
        if "first name" in lower or "first_name" in lower or "company" in lower:
            header_idx = i
            break

    if header_idx is None:
        print("Error: Could not detect CSV headers. Expected columns like")
        print("'First Name', 'Last Name', 'Company', 'Position'.")
        sys.exit(1)

    csv_text = "".join(raw_lines[header_idx:])
    reader = csv.reader(csv_text.splitlines())
    headers = next(reader)
    col_map = detect_csv_columns(headers)

    if col_map["company"] is None:
        print("Error: Could not find a 'Company' column in the CSV.")
        print(f"  Detected headers: {headers}")
        sys.exit(1)

    for row in reader:
        if not row or len(row) <= col_map["company"]:
            continue
        entry = {
            "first_name": row[col_map["first_name"]].strip() if col_map["first_name"] is not None and col_map["first_name"] < len(row) else "",
            "last_name": row[col_map["last_name"]].strip() if col_map["last_name"] is not None and col_map["last_name"] < len(row) else "",
            "company": row[col_map["company"]].strip() if col_map["company"] < len(row) else "",
            "position": row[col_map["position"]].strip() if col_map["position"] is not None and col_map["position"] < len(row) else "",
        }
        connections.append(entry)

    return connections


def find_utility_connections(connections, extra_companies=None, extra_keywords=None):
    """Filter connections to those working at utility companies."""
    return [c for c in connections if is_utility_company(c["company"], extra_companies, extra_keywords)]


def write_results_csv(matches, output_path):
    """Write matched connections to a CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["first_name", "last_name", "company", "position"])
        writer.writeheader()
        writer.writerows(matches)
    print(f"\nResults saved to: {output_path}")


def print_results(matches, total_count):
    """Print results to the terminal."""
    if not matches:
        print(f"\nScanned {total_count} connections — no utility company matches found.")
        print("\nTips:")
        print("  - Try adding custom keywords: --custom-keywords 'solar,wind,renewable'")
        print("  - Try adding company names:   --custom-companies 'My Local Power Co'")
        return

    print(f"\n{'='*70}")
    print(f"  Found {len(matches)} connection(s) at utility companies")
    print(f"  (out of {total_count} total connections)")
    print(f"{'='*70}\n")

    by_company = {}
    for m in matches:
        co = m["company"] or "(unknown)"
        by_company.setdefault(co, []).append(m)

    for company in sorted(by_company.keys(), key=str.lower):
        print(f"  {company}")
        print(f"  {'-' * len(company)}")
        for person in by_company[company]:
            name = f"{person['first_name']} {person['last_name']}".strip()
            pos = person["position"]
            if pos:
                print(f"    {name}  —  {pos}")
            else:
                print(f"    {name}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Find LinkedIn connections who work at utility companies (CSV mode).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How to export your LinkedIn connections:
  1. Go to LinkedIn > Settings & Privacy
  2. Click 'Data Privacy' > 'Get a copy of your data'
  3. Select 'Connections' and request the archive
  4. Download the CSV when LinkedIn emails it to you
  5. Run this script on the downloaded CSV file

For browser-based scraping (includes 2nd-degree connections), use:
  python linkedin_scraper.py --email you@example.com --depth 2

Examples:
  python linkedin_utility_finder.py Connections.csv
  python linkedin_utility_finder.py Connections.csv --output results.csv
  python linkedin_utility_finder.py Connections.csv --custom-keywords "solar,wind"
        """,
    )
    parser.add_argument("csv_file", help="Path to your LinkedIn Connections CSV export")
    parser.add_argument("--custom-keywords", default="", help="Additional keywords to match (comma-separated)")
    parser.add_argument("--custom-companies", default="", help="Additional company names to match (comma-separated)")
    parser.add_argument("--output", "-o", default="", help="Save results to a CSV file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show additional details")

    args = parser.parse_args()

    extra_keywords = [k.strip() for k in args.custom_keywords.split(",") if k.strip()] if args.custom_keywords else None
    extra_companies = [c.strip() for c in args.custom_companies.split(",") if c.strip()] if args.custom_companies else None

    if args.verbose:
        print(f"Reading: {args.csv_file}")

    connections = parse_connections_csv(args.csv_file)

    if args.verbose:
        print(f"Loaded {len(connections)} connections")

    matches = find_utility_connections(connections, extra_companies, extra_keywords)
    print_results(matches, len(connections))

    if args.output:
        write_results_csv(matches, args.output)


if __name__ == "__main__":
    main()
