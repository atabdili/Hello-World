# Hello-World
This is my test first repository
Here is the my first Change

## LinkedIn Utility Finder

A Python script that scans your LinkedIn connections export to find people who work at utility companies (electric, gas, water, etc.).

### How to Get Your LinkedIn Data

1. Go to **LinkedIn > Settings & Privacy**
2. Click **Data Privacy** > **Get a copy of your data**
3. Select **Connections** and click **Request archive**
4. Wait for LinkedIn to email you (usually within minutes)
5. Download and unzip the archive — you'll find a `Connections.csv` file

### Usage

```bash
# Basic scan
python linkedin_utility_finder.py Connections.csv

# Save results to a file
python linkedin_utility_finder.py Connections.csv --output results.csv

# Add custom keywords to broaden the search
python linkedin_utility_finder.py Connections.csv --custom-keywords "solar,wind,renewable"

# Add specific company names
python linkedin_utility_finder.py Connections.csv --custom-companies "My Local Power Co,Regional Water Authority"

# Verbose mode
python linkedin_utility_finder.py Connections.csv -v
```

### What It Matches

- **120+ known utility companies** (Duke Energy, PG&E, ConEd, American Water, etc.)
- **Keyword matching** for company names containing terms like "electric", "power", "gas", "water district", "energy company", etc.
- Covers electric, gas, water, and multi-utility companies

### Requirements

Python 3.6+ (no external dependencies — uses only the standard library)
