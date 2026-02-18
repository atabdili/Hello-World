"""
bill_parser.py
Parses raw bill text to extract structured payment information.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class BillInfo:
    """Structured data extracted from a scanned bill."""

    payee: Optional[str]          # Company/person to be paid
    amount_due: Optional[float]   # Total amount owed in USD
    due_date: Optional[date]      # Payment due date
    account_number: Optional[str] # Customer's account number on the bill
    invoice_number: Optional[str] # Invoice or bill reference number

    def is_complete(self) -> bool:
        """Return True if the minimum fields needed to schedule a payment are present."""
        return self.payee is not None and self.amount_due is not None

    def __str__(self) -> str:
        parts = [
            f"Payee        : {self.payee or 'unknown'}",
            f"Amount Due   : ${self.amount_due:.2f}" if self.amount_due else "Amount Due   : unknown",
            f"Due Date     : {self.due_date}" if self.due_date else "Due Date     : unknown",
            f"Account #    : {self.account_number or 'N/A'}",
            f"Invoice #    : {self.invoice_number or 'N/A'}",
        ]
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_amount(text: str) -> Optional[float]:
    """Find the largest dollar amount in the text, assumed to be the total due."""
    # Match patterns like "$1,234.56", "1,234.56", "USD 1234.56"
    pattern = r"""
        (?:total\s+(?:amount\s+)?due[:\s]+|amount\s+due[:\s]+|balance\s+due[:\s]+|
           please\s+pay[:\s]+|payment\s+due[:\s]+)
        \$?\s*([\d,]+\.?\d*)
        |
        \$\s*([\d,]+\.\d{2})
    """
    matches = re.findall(pattern, text, re.IGNORECASE | re.VERBOSE)

    candidates: list[float] = []
    for groups in matches:
        for raw in groups:
            if raw:
                try:
                    candidates.append(float(raw.replace(",", "")))
                except ValueError:
                    pass

    return max(candidates) if candidates else None


def _extract_due_date(text: str) -> Optional[date]:
    """Find a due date in various common formats."""
    # Patterns: "Due Date: 03/15/2024", "Payment Due: March 15, 2024", etc.
    date_patterns = [
        r"(?:due\s+date|payment\s+due|pay\s+by)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?:due\s+date|payment\s+due|pay\s+by)[:\s]+([A-Za-z]+ \d{1,2},?\s*\d{4})",
        r"(?:due\s+date|payment\s+due|pay\s+by)[:\s]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    ]
    formats = [
        "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y",
    ]

    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().rstrip(",")
            for fmt in formats:
                try:
                    return datetime.strptime(raw, fmt).date()
                except ValueError:
                    continue
    return None


def _extract_account_number(text: str) -> Optional[str]:
    """Extract the customer account number from the bill."""
    pattern = r"(?:account\s+(?:number|#|no\.?)[:\s]+)([A-Za-z0-9\-]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_invoice_number(text: str) -> Optional[str]:
    """Extract the invoice or bill number."""
    pattern = r"(?:invoice\s+(?:number|#|no\.?)|bill\s+(?:number|#|no\.?))[:\s]+([A-Za-z0-9\-]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_payee(text: str) -> Optional[str]:
    """
    Attempt to extract the payee (biller) name.
    Strategy: take the first non-empty line of text, as most bills start with
    the company name in the header.
    """
    for line in text.splitlines():
        clean = line.strip()
        # Skip lines that look like dates, amounts, or page numbers
        if clean and not re.match(r"^[\d/\-$,. ]+$", clean) and len(clean) >= 3:
            return clean[:80]  # Cap at 80 chars to avoid garbage
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_bill(raw_text: str) -> BillInfo:
    """
    Parse raw OCR/extracted text and return structured BillInfo.

    Parameters
    ----------
    raw_text : str
        Text extracted by bill_scanner.scan_bill().

    Returns
    -------
    BillInfo
        Populated as fully as the text allows; missing fields are None.
    """
    return BillInfo(
        payee=_extract_payee(raw_text),
        amount_due=_extract_amount(raw_text),
        due_date=_extract_due_date(raw_text),
        account_number=_extract_account_number(raw_text),
        invoice_number=_extract_invoice_number(raw_text),
    )
