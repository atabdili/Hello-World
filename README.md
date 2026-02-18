# Hello-World

This is my test first repository
Here is the my first Change

---

## Automated Bill Payment via Citibank

This tool scans paper or digital bills (PDF, JPG, PNG) and pays them automatically through your Citibank checking account using Citibank's OAuth 2.0 API.

### How it works

```
bill image/PDF
      │
      ▼
bill_scanner.py   ← OCR (Tesseract) or PDF text extraction
      │
      ▼
bill_parser.py    ← extract payee, amount, due date, account #
      │
      ▼
citibank_client.py ← Citibank API: verify balance, schedule payment
      │
      ▼
  Payment scheduled ✓
```

### Prerequisites

**System dependency – Tesseract OCR** (needed for image bills):

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt install tesseract-ocr

# Windows
# Download installer from https://github.com/tesseract-ocr/tesseract
```

**Python dependencies:**

```bash
pip install -r requirements.txt
```

### Setup

1. Register an application at [developer.citi.com](https://developer.citi.com) and obtain a `client_id` and `client_secret`.

2. Copy the example environment file and fill in your credentials:

   ```bash
   cp .env.example .env
   # Edit .env with your Citibank API credentials and checking account ID
   ```

3. Authorize the app with your Citibank account (one-time step):

   ```bash
   python pay_bill.py auth
   ```

   This prints an authorization URL. Open it in your browser, approve access, then paste the returned code back into the terminal. Save the printed `access_token`.

### Usage

**Preview a bill without paying:**

```bash
python pay_bill.py scan electric_bill.pdf
```

**Pay a bill (interactive confirmation):**

```bash
python pay_bill.py pay electric_bill.pdf --token <access_token>
```

**Pay a bill on a specific date:**

```bash
python pay_bill.py pay water_bill.jpg --token <access_token> --date 2024-04-15
```

**Override extracted fields when OCR is uncertain:**

```bash
python pay_bill.py pay invoice.pdf \
    --token <access_token> \
    --payee "Pacific Gas & Electric" \
    --amount 134.72
```

**Dry run (validate without submitting payment):**

```bash
python pay_bill.py pay invoice.pdf --token <access_token> --dry-run
```

**Store the access token in `.env` to avoid passing it every time:**

```
CITI_ACCESS_TOKEN=your_access_token_here
```

### File structure

| File | Purpose |
|------|---------|
| `pay_bill.py` | CLI entry point |
| `bill_scanner.py` | OCR / PDF text extraction |
| `bill_parser.py` | Regex-based field extraction |
| `citibank_client.py` | Citibank OAuth 2.0 + payment API |
| `.env.example` | Template for credentials |
| `requirements.txt` | Python dependencies |

### Security notes

- Never commit `.env` to version control (it is already in `.gitignore`).
- Access tokens expire; re-run `python pay_bill.py auth` or implement token refresh with the `refresh_access_token()` function in `citibank_client.py`.
- Use the sandbox environment (`CITI_ENV=sandbox`) for testing before switching to production.
