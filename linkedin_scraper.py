#!/usr/bin/env python3
"""
LinkedIn Utility Finder — Browser Scraper

Logs into LinkedIn using Selenium, walks through your connections (and
optionally their connections), and identifies anyone who works at a
utility company.

Usage:
    python linkedin_scraper.py --email you@example.com
    python linkedin_scraper.py --email you@example.com --depth 2
    python linkedin_scraper.py --email you@example.com --depth 2 --output results.csv

The script will prompt for your password (never stored). If LinkedIn asks
for a verification code (2FA / CAPTCHA), the script pauses and lets you
handle it in the browser before continuing.

WARNING: Automated access to LinkedIn may violate their Terms of Service
and could result in account restrictions. Use at your own risk.
"""

import argparse
import csv
import getpass
import json
import random
import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    print("Error: selenium is required. Install it with:")
    print("  pip install selenium")
    sys.exit(1)

from utility_matcher import is_utility_company

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
CONNECTIONS_URL = "https://www.linkedin.com/mynetwork/invite-connect/connections/"

# Be polite — random delays between actions (seconds)
MIN_DELAY = 2
MAX_DELAY = 5
PAGE_LOAD_DELAY = 3

# How many times to scroll to load more connections on a page
MAX_SCROLLS = 50


def human_delay(minimum=MIN_DELAY, maximum=MAX_DELAY):
    """Sleep for a random human-like interval."""
    time.sleep(random.uniform(minimum, maximum))


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------
def create_driver(headless=False):
    """Create and return a Chrome WebDriver."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Make automation less detectable
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # Override navigator.webdriver flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login(driver, email, password):
    """Log into LinkedIn. Returns True on success."""
    print("Navigating to LinkedIn login...")
    driver.get(LINKEDIN_LOGIN_URL)
    human_delay(2, 4)

    try:
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_field = driver.find_element(By.ID, "password")

        email_field.clear()
        email_field.send_keys(email)
        human_delay(0.5, 1.5)
        password_field.clear()
        password_field.send_keys(password)
        human_delay(0.5, 1.0)
        password_field.send_keys(Keys.RETURN)
    except Exception as e:
        print(f"Error during login form fill: {e}")
        return False

    # Wait for either the feed to load (success) or a challenge page
    print("Waiting for login to complete...")
    time.sleep(5)

    # Check if we hit a verification/challenge page
    current_url = driver.current_url
    if "checkpoint" in current_url or "challenge" in current_url:
        print("\n" + "=" * 60)
        print("  LinkedIn is asking for additional verification.")
        print("  Please complete the challenge in the browser window,")
        print("  then press ENTER here to continue.")
        print("=" * 60)
        input("\nPress ENTER after completing verification... ")
        time.sleep(3)

    # Verify we're logged in
    current_url = driver.current_url
    if "feed" in current_url or "mynetwork" in current_url or "linkedin.com/in/" in current_url:
        print("Login successful!")
        return True

    # One more check — look for the nav bar that only appears when logged in
    try:
        driver.find_element(By.CSS_SELECTOR, ".global-nav")
        print("Login successful!")
        return True
    except Exception:
        pass

    print("Login may have failed. Current URL:", current_url)
    print("If you see the LinkedIn feed, press ENTER to continue anyway.")
    print("Otherwise, press Ctrl+C to abort.")
    input("\nPress ENTER to continue... ")
    return True


# ---------------------------------------------------------------------------
# Scraping connections
# ---------------------------------------------------------------------------
def scroll_to_load_all(driver, max_scrolls=MAX_SCROLLS):
    """Scroll down to load all lazy-loaded connection cards."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_delay(1.5, 3.0)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    # Scroll back to top
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def extract_connection_cards(driver):
    """Extract name, headline, and profile URL from connection cards on the current page."""
    connections = []
    cards = driver.find_elements(By.CSS_SELECTOR, "li.mn-connection-card")

    # Fallback selectors if the above doesn't match (LinkedIn updates its markup)
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-view-name='connection-card']")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, ".scaffold-finite-scroll__content li")

    for card in cards:
        try:
            # Try to get the name
            name_el = None
            for sel in [
                ".mn-connection-card__name",
                ".entity-result__title-text a span[aria-hidden='true']",
                "span.mn-connection-card__name",
                ".artdeco-entity-lockup__title span[aria-hidden='true']",
            ]:
                try:
                    name_el = card.find_element(By.CSS_SELECTOR, sel)
                    if name_el:
                        break
                except Exception:
                    continue

            name = name_el.text.strip() if name_el else ""

            # Try to get the headline (usually contains "Title at Company")
            headline_el = None
            for sel in [
                ".mn-connection-card__occupation",
                ".entity-result__primary-subtitle",
                "span.mn-connection-card__occupation",
                ".artdeco-entity-lockup__subtitle",
            ]:
                try:
                    headline_el = card.find_element(By.CSS_SELECTOR, sel)
                    if headline_el:
                        break
                except Exception:
                    continue

            headline = headline_el.text.strip() if headline_el else ""

            # Try to get the profile link
            link_el = None
            for sel in [
                "a.mn-connection-card__link",
                "a.app-aware-link",
                "a[href*='/in/']",
            ]:
                try:
                    link_el = card.find_element(By.CSS_SELECTOR, sel)
                    if link_el:
                        break
                except Exception:
                    continue

            profile_url = link_el.get_attribute("href") if link_el else ""

            if name:
                connections.append({
                    "name": name,
                    "headline": headline,
                    "profile_url": profile_url,
                    "degree": 1,
                    "via": "direct",
                })
        except Exception:
            continue

    return connections


def parse_headline(headline):
    """Parse a LinkedIn headline like 'Senior Engineer at Duke Energy' into (position, company)."""
    if not headline:
        return "", ""

    # Common patterns: "Title at Company" or "Title @ Company"
    for separator in [" at ", " @ ", " - "]:
        if separator in headline:
            parts = headline.split(separator, 1)
            return parts[0].strip(), parts[1].strip()

    # If no separator found, the whole thing might be a company or title
    return "", headline.strip()


def get_my_connections(driver, verbose=False):
    """Navigate to connections page and scrape all 1st-degree connections."""
    print("\nLoading your connections page...")
    driver.get(CONNECTIONS_URL)
    human_delay(PAGE_LOAD_DELAY, PAGE_LOAD_DELAY + 2)

    print("Scrolling to load all connections (this may take a while)...")
    scroll_to_load_all(driver)

    connections = extract_connection_cards(driver)
    print(f"Found {len(connections)} direct connections.")

    if verbose and connections:
        print(f"  First: {connections[0]['name']}")
        print(f"  Last:  {connections[-1]['name']}")

    return connections


def get_connections_of(driver, profile_url, owner_name, verbose=False):
    """Visit a connection's profile and try to scrape their connections list."""
    second_degree = []

    # Navigate to their connections page
    # LinkedIn profile URLs look like: https://www.linkedin.com/in/username/
    # Their connections page is: https://www.linkedin.com/in/username/connections/ (if visible)
    if not profile_url:
        return second_degree

    # Normalize the URL
    profile_url = profile_url.rstrip("/")
    connections_page = profile_url + "/details/connections/"

    if verbose:
        print(f"  Visiting connections of: {owner_name}")

    driver.get(connections_page)
    human_delay(PAGE_LOAD_DELAY, PAGE_LOAD_DELAY + 2)

    # Check if we can see their connections or if it's restricted
    page_source = driver.page_source.lower()
    if "this profile's connections aren't visible" in page_source or \
       "you don't have access" in page_source or \
       "page not found" in page_source:
        if verbose:
            print(f"    -> Connections not visible for {owner_name}")
        return second_degree

    # Scroll to load connections
    scroll_to_load_all(driver, max_scrolls=15)

    # Try to extract connection info from this page
    # The layout differs from the main connections page; try multiple selectors
    cards = driver.find_elements(By.CSS_SELECTOR, "li.reusable-search__result-container")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-view-name='search-entity-result-universal-template']")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, ".scaffold-finite-scroll__content li")

    for card in cards:
        try:
            name = ""
            headline = ""

            # Name
            for sel in [
                "span.entity-result__title-text a span[aria-hidden='true']",
                ".artdeco-entity-lockup__title span[aria-hidden='true']",
                "span[aria-hidden='true']",
            ]:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el and el.text.strip():
                        name = el.text.strip()
                        break
                except Exception:
                    continue

            # Headline
            for sel in [
                ".entity-result__primary-subtitle",
                ".artdeco-entity-lockup__subtitle",
                "div.entity-result__primary-subtitle",
            ]:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el and el.text.strip():
                        headline = el.text.strip()
                        break
                except Exception:
                    continue

            if name:
                second_degree.append({
                    "name": name,
                    "headline": headline,
                    "profile_url": "",
                    "degree": 2,
                    "via": owner_name,
                })
        except Exception:
            continue

    if verbose:
        print(f"    -> Found {len(second_degree)} connections of {owner_name}")

    return second_degree


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def print_results(matches, total_scanned, depth):
    """Print the utility matches to the terminal."""
    if not matches:
        print(f"\nScanned {total_scanned} connections (depth={depth}) — no utility matches found.")
        return

    # Separate by degree
    first_degree = [m for m in matches if m["degree"] == 1]
    second_degree = [m for m in matches if m["degree"] == 2]

    print(f"\n{'='*70}")
    print(f"  Found {len(matches)} connection(s) at utility companies")
    print(f"  ({len(first_degree)} direct, {len(second_degree)} via connections)")
    print(f"  Scanned {total_scanned} total profiles")
    print(f"{'='*70}")

    if first_degree:
        print(f"\n--- Your Direct Connections (1st degree) ---\n")
        _print_group(first_degree)

    if second_degree:
        print(f"\n--- Connections of Connections (2nd degree) ---\n")
        _print_group(second_degree, show_via=True)


def _print_group(matches, show_via=False):
    """Print a group of matches, grouped by company."""
    by_company = {}
    for m in matches:
        _, company = parse_headline(m["headline"])
        co = company or "(unknown)"
        by_company.setdefault(co, []).append(m)

    for company in sorted(by_company.keys(), key=str.lower):
        print(f"  {company}")
        print(f"  {'-' * len(company)}")
        for person in by_company[company]:
            position, _ = parse_headline(person["headline"])
            line = f"    {person['name']}"
            if position:
                line += f"  —  {position}"
            if show_via and person.get("via"):
                line += f"  (via {person['via']})"
            print(line)
        print()


def save_results_csv(matches, output_path):
    """Save matches to a CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Position", "Company", "Degree", "Via", "Profile URL"])
        for m in matches:
            position, company = parse_headline(m["headline"])
            writer.writerow([
                m["name"],
                position,
                company,
                m["degree"],
                m.get("via", ""),
                m.get("profile_url", ""),
            ])
    print(f"\nResults saved to: {output_path}")


def save_progress(all_connections, filepath="linkedin_scrape_progress.json"):
    """Save scraped connections to a JSON file for resuming later."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(all_connections, f, indent=2)


def load_progress(filepath="linkedin_scrape_progress.json"):
    """Load previously scraped connections from a JSON file."""
    path = Path(filepath)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn connections to find people at utility companies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WARNING: Automated access to LinkedIn may violate their Terms of Service
and could result in account restrictions. Use at your own risk.

Examples:
  # Scan only your direct connections
  python linkedin_scraper.py --email you@example.com

  # Also scan connections-of-connections (2nd degree)
  python linkedin_scraper.py --email you@example.com --depth 2

  # Save results to CSV
  python linkedin_scraper.py --email you@example.com --depth 2 -o results.csv

  # Limit how many connections' networks to scan (faster)
  python linkedin_scraper.py --email you@example.com --depth 2 --max-profiles 50

  # Resume a previous scrape
  python linkedin_scraper.py --email you@example.com --depth 2 --resume
        """,
    )
    parser.add_argument("--email", required=True, help="Your LinkedIn email address")
    parser.add_argument("--depth", type=int, default=1, choices=[1, 2],
                        help="1 = your connections only, 2 = also their connections (default: 1)")
    parser.add_argument("--max-profiles", type=int, default=0,
                        help="Max number of connections to visit for 2nd-degree scraping (0 = all)")
    parser.add_argument("--output", "-o", default="", help="Save results to a CSV file")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (no visible window)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from a previous scrape (uses linkedin_scrape_progress.json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")
    parser.add_argument("--custom-keywords", default="",
                        help="Additional utility keywords (comma-separated)")
    parser.add_argument("--custom-companies", default="",
                        help="Additional utility company names (comma-separated)")

    args = parser.parse_args()

    extra_keywords = [k.strip() for k in args.custom_keywords.split(",") if k.strip()] if args.custom_keywords else None
    extra_companies = [c.strip() for c in args.custom_companies.split(",") if c.strip()] if args.custom_companies else None

    password = getpass.getpass("LinkedIn password (input is hidden): ")

    # Check for resume
    all_connections = []
    visited_profiles = set()

    if args.resume:
        progress = load_progress()
        if progress:
            all_connections = progress
            visited_profiles = {c["profile_url"] for c in all_connections if c.get("profile_url")}
            print(f"Resumed {len(all_connections)} connections from previous scrape.")
        else:
            print("No previous progress file found. Starting fresh.")

    print("\nStarting browser...")
    driver = create_driver(headless=args.headless)

    try:
        if not login(driver, args.email, password):
            print("Could not log in. Exiting.")
            return

        # --- 1st degree: your connections ---
        if not args.resume or not any(c["degree"] == 1 for c in all_connections):
            my_connections = get_my_connections(driver, verbose=args.verbose)
            all_connections.extend(my_connections)
            save_progress(all_connections)
            print(f"Progress saved ({len(all_connections)} connections so far).")
        else:
            my_connections = [c for c in all_connections if c["degree"] == 1]
            print(f"Using {len(my_connections)} 1st-degree connections from previous scrape.")

        # --- 2nd degree: connections of connections ---
        if args.depth >= 2:
            profiles_to_visit = [
                c for c in my_connections
                if c.get("profile_url") and c["profile_url"] not in visited_profiles
            ]

            if args.max_profiles > 0:
                profiles_to_visit = profiles_to_visit[:args.max_profiles]

            total = len(profiles_to_visit)
            print(f"\nScanning connections of {total} profiles for 2nd-degree matches...")

            for i, conn in enumerate(profiles_to_visit, 1):
                print(f"  [{i}/{total}] {conn['name']}...", end="", flush=True)

                second_deg = get_connections_of(
                    driver, conn["profile_url"], conn["name"], verbose=args.verbose
                )
                if second_deg:
                    print(f" {len(second_deg)} found")
                    all_connections.extend(second_deg)
                else:
                    print(" (no access or empty)")

                visited_profiles.add(conn["profile_url"])

                # Save progress periodically
                if i % 10 == 0:
                    save_progress(all_connections)
                    print(f"  Progress saved ({len(all_connections)} total connections).")

                # Random delay between profile visits
                human_delay(3, 7)

            save_progress(all_connections)

    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving progress...")
        save_progress(all_connections)
        print("Progress saved. Use --resume to continue later.")
    finally:
        driver.quit()
        print("Browser closed.")

    # --- Filter for utility companies ---
    print("\nFiltering for utility company connections...")
    matches = []
    for conn in all_connections:
        _, company = parse_headline(conn.get("headline", ""))
        if is_utility_company(company, extra_companies, extra_keywords):
            matches.append(conn)

    # Also check the full headline in case the company name is embedded differently
    seen = {(m["name"], m.get("headline", "")) for m in matches}
    for conn in all_connections:
        key = (conn["name"], conn.get("headline", ""))
        if key not in seen and is_utility_company(conn.get("headline", ""), extra_companies, extra_keywords):
            matches.append(conn)

    print_results(matches, len(all_connections), args.depth)

    if args.output:
        save_results_csv(matches, args.output)


if __name__ == "__main__":
    main()
