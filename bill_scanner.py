"""
bill_scanner.py
Extracts raw text from bill images and PDFs using OCR.
"""

import os
from pathlib import Path


def scan_image(file_path: str) -> str:
    """Extract text from a bill image (JPG, PNG, TIFF, etc.) using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Image scanning requires pytesseract and Pillow. "
            "Run: pip install pytesseract Pillow"
        ) from exc

    image = Image.open(file_path)
    # Use page segmentation mode 6 (uniform block of text) for typical bill layouts
    text = pytesseract.image_to_string(image, config="--psm 6")
    return text


def scan_pdf(file_path: str) -> str:
    """Extract text from a bill PDF, using embedded text first then OCR fallback."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF scanning requires pdfplumber. Run: pip install pdfplumber"
        ) from exc

    pages_text: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text.strip():
                # Fallback: render page as image and OCR it
                image = page.to_image(resolution=300).original
                try:
                    import pytesseract
                    text = pytesseract.image_to_string(image, config="--psm 6")
                except ImportError:
                    pass  # Skip OCR fallback if pytesseract not available
            pages_text.append(text)

    return "\n".join(pages_text)


def scan_bill(file_path: str) -> str:
    """
    Auto-detect file type and extract text from the bill.

    Supports: PDF, JPG, JPEG, PNG, TIFF, BMP, GIF
    Returns raw extracted text.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Bill file not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return scan_pdf(file_path)
    elif suffix in {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif"}:
        return scan_image(file_path)
    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            "Supported types: PDF, JPG, PNG, TIFF, BMP, GIF"
        )
