"""
BIBLIOnomics Lambda — API Clients
HTTP clients for BiblioShare, Google Books, and Open Library with retry logic.
"""

import os
import time
import requests

from config import (
    BIBLIOSHARE_ENDPOINT,
    GOOGLE_BOOKS_ENDPOINT,
    OPEN_LIBRARY_ENDPOINT,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
)


def fetch_with_retry(url, timeout=5):
    """GET with exponential-backoff retry driven by config constants."""
    for attempt in range(MAX_RETRIES):
        try:
            res = requests.get(url, timeout=timeout)
            if res.status_code == 200:
                return res
            if res.status_code in (429, 503):
                time.sleep(RETRY_BACKOFF_FACTOR ** (attempt + 1))
        except requests.exceptions.RequestException as e:
            print(f"Request error [{url}]: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_FACTOR ** (attempt + 1))
    return None


def fetch_biblioshare(isbn):
    """
    Fetch ONIX XML from BiblioShare for the given ISBN-13.
    Returns raw XML string or None on failure.
    """
    token = os.environ.get('BIBLIOSHARE_TOKEN')
    if not token:
        print("Missing BIBLIOSHARE_TOKEN.")
        return None
    
    try:
        res = fetch_with_retry(
            f"{BIBLIOSHARE_ENDPOINT}?Token={token}&EAN={isbn}",
            timeout=8
        )
        if not res:
            return None
        
        # Return raw XML content for parsing in onix_parser module
        return res.content
        
    except Exception as e:
        print(f"BiblioShare Error: {e}")
        return None


def fetch_google_books(isbn):
    """
    Fetch rating and metadata from Google Books API.
    Returns volumeInfo dict or None.
    """
    try:
        res = fetch_with_retry(f"{GOOGLE_BOOKS_ENDPOINT}?q=isbn:{isbn}")
        if res:
            data = res.json()
            total_items = data.get('totalItems', 0)
            
            if 'items' in data and total_items > 0:
                # If exactly 1 item, return it (exact match)
                if total_items == 1:
                    return data['items'][0]['volumeInfo']
                
                # If more than 1 but <= 5 items, validate ISBN13 match
                elif 1 < total_items <= 5:
                    for item in data['items']:
                        volume_info = item.get('volumeInfo', {})
                        identifiers = volume_info.get('industryIdentifiers', [])
                        
                        for identifier in identifiers:
                            if identifier.get('type') == 'ISBN_13' and identifier.get('identifier') == isbn:
                                print(f"Google Books: Found exact ISBN13 match for {isbn} in {total_items} results")
                                return volume_info
                    
                    # No exact ISBN13 match found
                    print(f"Google Books: No exact ISBN13 match for {isbn} in {total_items} results")
                    return None
                
                # If more than 5 items, no exact match expected
                else:
                    print(f"Google Books: Too many results ({total_items}) for {isbn}, no exact match expected")
                    return None
                    
    except Exception as e:
        print(f"Google Books Error: {e}")
    return None


def fetch_open_library(isbn):
    """
    Check book availability on Open Library.
    Returns dict or None.
    """
    try:
        res = fetch_with_retry(OPEN_LIBRARY_ENDPOINT.format(isbn=isbn))
        if res:
            return res.json()
    except Exception as e:
        print(f"Open Library Error: {e}")
    return None