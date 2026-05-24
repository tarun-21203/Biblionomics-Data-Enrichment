"""
BIBLIOnomics Lambda — HTML Utilities
Robust HTML cleaning using BeautifulSoup for better entity and tag handling.
"""

import html
import re

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("Warning: BeautifulSoup not available, falling back to regex-based HTML stripping")


def clean_html(text):
    """
    Clean HTML content with double-unescape and robust tag stripping.
    Uses BeautifulSoup if available, falls back to regex.
    """
    if not text:
        return ""
    
    # Double-unescape to handle double-encoded entities like &amp;lt;p&amp;gt;
    text = html.unescape(html.unescape(text))
    
    if HAS_BS4:
        # BeautifulSoup handles malformed HTML and mixed encoding far more
        # robustly than regex stripping
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
    else:
        # Fallback: regex-based stripping (less robust)
        text = re.sub(r'<[^>]+>', ' ', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def strip_html(text):
    """Alias for clean_html for backward compatibility."""
    return clean_html(text)