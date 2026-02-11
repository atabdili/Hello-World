#!/usr/bin/env python3
"""
LinkedIn Utility Finder

Scans your LinkedIn connections export (CSV) to find people who work at
utility companies (electric, gas, water, etc.).

Usage:
    1. Export your LinkedIn connections:
       LinkedIn > Settings > Data Privacy > Get a copy of your data > Connections
    2. Download the CSV file when LinkedIn emails it to you
    3. Run: python linkedin_utility_finder.py Connections.csv

Options:
    --custom-keywords   Add extra keywords to search for (comma-separated)
    --custom-companies  Add extra company names to match (comma-separated)
    --output            Save results to a CSV file
    --verbose           Show all connections, not just matches
"""

import argparse
import csv
import sys
from pathlib import Path


# --- Known utility companies (US-focused, expandable) ---
KNOWN_UTILITY_COMPANIES = {
    # Electric
    "duke energy",
    "southern company",
    "dominion energy",
    "nextera energy",
    "exelon",
    "american electric power",
    "aep",
    "entergy",
    "firstenergy",
    "xcel energy",
    "eversource energy",
    "eversource",
    "consolidated edison",
    "con edison",
    "coned",
    "pacific gas and electric",
    "pacific gas & electric",
    "pg&e",
    "pge",
    "southern california edison",
    "sce",
    "florida power & light",
    "florida power and light",
    "fpl",
    "georgia power",
    "virginia electric and power",
    "dominion virginia power",
    "commonwealth edison",
    "comed",
    "peco energy",
    "baltimore gas and electric",
    "bge",
    "pepco",
    "atlantic city electric",
    "delmarva power",
    "consumers energy",
    "dte energy",
    "dte",
    "we energies",
    "wisconsin energy",
    "alliant energy",
    "ameren",
    "evergy",
    "westar energy",
    "kansas city power and light",
    "kcpl",
    "empire district electric",
    "avista",
    "idaho power",
    "portland general electric",
    "puget sound energy",
    "pacificorp",
    "rocky mountain power",
    "tucson electric power",
    "arizona public service",
    "aps",
    "salt river project",
    "srp",
    "nevada energy",
    "nv energy",
    "hawaiian electric",
    "heco",
    "entergy arkansas",
    "entergy louisiana",
    "entergy mississippi",
    "entergy texas",
    "cleco",
    "oncor",
    "centerpoint energy",
    "atmos energy",
    "sempra energy",
    "san diego gas & electric",
    "san diego gas and electric",
    "sdg&e",
    "national grid",
    "pseg",
    "public service enterprise group",
    "ppl corporation",
    "ppl electric",
    "algonquin power",
    "avangrid",
    "cms energy",
    "pinnacle west",
    "oge energy",
    "oklahoma gas and electric",
    "black hills energy",
    "el paso electric",
    "green mountain power",
    "unitil",
    "liberty utilities",
    "new england power",
    "berkshire hathaway energy",
    "midamerican energy",
    "tampa electric",
    "teco energy",
    # Gas
    "southern union",
    "spire",
    "laclede gas",
    "new jersey resources",
    "south jersey industries",
    "southwest gas",
    "nicor gas",
    "peoples gas",
    "columbia gas",
    "nisource",
    "piedmont natural gas",
    "questar",
    "washington gas",
    "wgl holdings",
    # Water
    "american water works",
    "american water",
    "aqua america",
    "essential utilities",
    "california water service",
    "sjw group",
    "york water",
    "middlesex water",
    "artesian resources",
    "connecticut water",
    "american states water",
    "suez water",
    "veolia water",
    "veolia",
    # Multi-utility / Holding
    "berkshire hathaway energy",
    "emera",
    "fortis",
    "hydro one",
    "ontario power generation",
    "bc hydro",
    "edf energy",
    "engie",
    "iberdrola",
    "enel",
    "eon",
    "e.on",
    "rwe",
    # Municipal / cooperative keywords handled by UTILITY_KEYWORDS below
}

# --- Keywords that suggest a utility company ---
UTILITY_KEYWORDS = [
    "electric",
    "electricity",
    "power company",
    "power authority",
    "power & light",
    "power and light",
    "energy company",
    "energy corp",
    "gas & electric",
    "gas and electric",
    "public utility",
    "public utilities",
    "utility district",
    "utility commission",
    "water authority",
    "water district",
    "water company",
    "water service",
    "water works",
    "waterworks",
    "municipal utility",
    "municipal electric",
    "cooperative electric",
    "electric cooperative",
    "electric co-op",
    "rural electric",
    "light and power",
    "light & power",
    "hydro",
    "hydroelectric",
    "nuclear power",
    "transmission",
    "grid operator",
    "independent system operator",
    "iso-ne",
    "ercot",
    "caiso",
    "pjm interconnection",
    "miso energy",
    "spp",
    "natural gas",
    "gas utility",
    "sewage",
    "sewer authority",
    "wastewater",
]


def detect_csv_columns(headers):
    """Detect which columns contain the relevant data.

    LinkedIn's export format has changed over the years. Common column names:
    - "First Name", "Last Name", "Company", "Position"
    - "first_name", "last_name", "company", "title"
    """
    headers_lower = [h.strip().lower() for h in headers]

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

    for i, h in enumerate(headers_lower):
        if h in first_name_candidates:
            col_map["first_name"] = i
        elif h in last_name_candidates:
            col_map["last_name"] = i
        elif h in company_candidates:
            col_map["company"] = i
        elif h in position_candidates:
            col_map["position"] = i

    return col_map


def is_utility_company(company_name, extra_companies=None, extra_keywords=None):
    """Check if a company name matches a known utility or utility keyword."""
    if not company_name:
        return False

    name_lower = company_name.strip().lower()

    if not name_lower:
        return False

    # Check against known utility companies
    all_companies = KNOWN_UTILITY_COMPANIES
    if extra_companies:
        all_companies = all_companies | {c.lower().strip() for c in extra_companies}

    if name_lower in all_companies:
        return True

    # Check if any known company name is contained within the company field
    for known in all_companies:
        if known in name_lower or name_lower in known:
            return True

    # Check for keyword matches
    all_keywords = UTILITY_KEYWORDS
    if extra_keywords:
        all_keywords = all_keywords + [k.lower().strip() for k in extra_keywords]

    for keyword in all_keywords:
        if keyword in name_lower:
            return True

    return False


def parse_connections_csv(filepath):
    """Parse a LinkedIn connections CSV and return rows as dicts."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    connections = []

    # LinkedIn CSVs sometimes have a few junk lines at the top; try to
    # detect the header row by looking for a line that contains "First Name"
    # or "first_name" or "Company".
    with open(path, newline="", encoding="utf-8-sig") as f:
        # Read all lines to find the header
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
    matches = []
    for conn in connections:
        if is_utility_company(conn["company"], extra_companies, extra_keywords):
            matches.append(conn)
    return matches


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

    # Group by company
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
        description="Find LinkedIn connections who work at utility companies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How to export your LinkedIn connections:
  1. Go to LinkedIn > Settings & Privacy
  2. Click 'Data Privacy' > 'Get a copy of your data'
  3. Select 'Connections' and request the archive
  4. Download the CSV when LinkedIn emails it to you
  5. Run this script on the downloaded CSV file

Examples:
  python linkedin_utility_finder.py Connections.csv
  python linkedin_utility_finder.py Connections.csv --output results.csv
  python linkedin_utility_finder.py Connections.csv --custom-keywords "solar,wind"
  python linkedin_utility_finder.py Connections.csv --custom-companies "My Local Utility"
        """,
    )
    parser.add_argument(
        "csv_file",
        help="Path to your LinkedIn Connections CSV export",
    )
    parser.add_argument(
        "--custom-keywords",
        help="Additional keywords to match (comma-separated)",
        default="",
    )
    parser.add_argument(
        "--custom-companies",
        help="Additional company names to match (comma-separated)",
        default="",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save results to a CSV file",
        default="",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show additional details during processing",
    )

    args = parser.parse_args()

    extra_keywords = [k.strip() for k in args.custom_keywords.split(",") if k.strip()] if args.custom_keywords else None
    extra_companies = [c.strip() for c in args.custom_companies.split(",") if c.strip()] if args.custom_companies else None

    if args.verbose:
        print(f"Reading: {args.csv_file}")
        if extra_keywords:
            print(f"Extra keywords: {extra_keywords}")
        if extra_companies:
            print(f"Extra companies: {extra_companies}")

    connections = parse_connections_csv(args.csv_file)

    if args.verbose:
        print(f"Loaded {len(connections)} connections")

    matches = find_utility_connections(connections, extra_companies, extra_keywords)
    print_results(matches, len(connections))

    if args.output:
        write_results_csv(matches, args.output)


if __name__ == "__main__":
    main()
