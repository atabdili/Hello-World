# Hello-World
This is my test first repository
Here is the my first Change

## LinkedIn Utility Finder

Find people in your LinkedIn network (and their networks) who work at utility companies — electric, gas, water, etc.

Two modes are available:

| Mode | What it does | Needs |
|------|-------------|-------|
| **CSV mode** | Scans your LinkedIn data export for utility connections | Just Python |
| **Browser mode** | Logs into LinkedIn, scrapes your connections AND their connections (2nd degree) | Python + Selenium + Chrome |

### Setup

```bash
pip install -r requirements.txt
```

You also need [Google Chrome](https://www.google.com/chrome/) installed (Selenium drives it automatically).

### Mode 1: CSV Export (quick, 1st-degree only)

Best for a fast scan of just your direct connections.

1. Go to **LinkedIn > Settings & Privacy > Data Privacy > Get a copy of your data**
2. Select **Connections**, request the archive, download the CSV
3. Run:

```bash
python linkedin_utility_finder.py Connections.csv
python linkedin_utility_finder.py Connections.csv --output results.csv
python linkedin_utility_finder.py Connections.csv --custom-keywords "solar,wind"
```

### Mode 2: Browser Scraper (deep, 1st + 2nd degree)

Logs into LinkedIn, walks through your connections, then visits each connection's profile to scan *their* connections too.

```bash
# Scan your direct connections only
python linkedin_scraper.py --email you@example.com

# Scan your connections AND their connections (2nd degree)
python linkedin_scraper.py --email you@example.com --depth 2

# Limit to first 50 profiles (faster)
python linkedin_scraper.py --email you@example.com --depth 2 --max-profiles 50

# Save results to CSV
python linkedin_scraper.py --email you@example.com --depth 2 -o results.csv

# Resume a previous scrape if interrupted
python linkedin_scraper.py --email you@example.com --depth 2 --resume
```

The script will:
- Prompt for your password (never stored)
- Open a Chrome window so you can see what's happening
- Pause if LinkedIn asks for 2FA / verification (you complete it manually)
- Save progress to `linkedin_scrape_progress.json` so you can resume if interrupted
- Add random delays between actions to be gentle

**Note:** Automated access to LinkedIn may violate their Terms of Service. Use at your own risk.

### What It Matches

- **120+ known utility companies** (Duke Energy, PG&E, ConEd, American Water, etc.)
- **Keyword matching** for company names containing terms like "electric", "power", "gas", "water district", "energy company", etc.
- Covers electric, gas, water, and multi-utility companies
- Add your own with `--custom-keywords` and `--custom-companies`

### Project Files

| File | Purpose |
|------|---------|
| `linkedin_utility_finder.py` | CSV-based scanner (1st degree) |
| `linkedin_scraper.py` | Browser-based scraper (1st + 2nd degree) |
| `utility_matcher.py` | Shared utility company matching logic |
| `requirements.txt` | Python dependencies |

### Requirements

- Python 3.6+
- Google Chrome
- `selenium` (installed via `pip install -r requirements.txt`)
