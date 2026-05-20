import json
import boto3
import requests
import os
import xml.etree.ElementTree as ET
from datetime import datetime

# Initialize the Comprehend client
comprehend = boto3.client('comprehend')

def fetch_google_books(isbn):
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200 and 'items' in res.json():
            return res.json()['items'][0]['volumeInfo']
    except Exception as e:
        print(f"Google Books API Error: {e}")
    return None

def fetch_open_library(isbn):
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return data.get(f"ISBN:{isbn}")
    except Exception as e:
        print(f"Open Library API Error: {e}")
    return None

def fetch_biblioshare(isbn):
    """
    Fetches the ONIX data from BiblioShare and extracts the biography.
    """
    token = os.environ.get('BIBLIOSHARE_TOKEN')
    if not token:
        print("Missing BIBLIOSHARE_TOKEN environment variable.")
        return {"bio": ""}
        
    try:
        # Using the exact endpoint provided
        url = f"https://biblioshare.ca/BNCServices/BNCServices.asmx/ONIX?Token={token}&EAN={isbn}"
        res = requests.get(url, timeout=5)
        
        if res.status_code == 200:
            # Parse the XML response
            root = ET.fromstring(res.content)
            bio_text = ""
            
            # ONIX often stores bios in <BiographicalNote> tags
            for bio_elem in root.iter('BiographicalNote'):
                if bio_elem.text:
                    bio_text = bio_elem.text
                    break
            
            # Fallback for ONIX 3.0 which might just use <Text> tags for descriptions/bios
            if not bio_text:
                for text_elem in root.iter('Text'):
                    if text_elem.text and len(text_elem.text) > 50: # Assuming bio is a substantial string
                        bio_text = text_elem.text
                        break
                        
            return {"bio": bio_text.strip()}
    except Exception as e:
        print(f"BiblioShare API Error: {e}")
        
    return {"bio": ""}

def calculate_confidence(book_data, comprehend_entities):
    score = 30 # Base score

    # Core fields completion
    if book_data.get('title') and book_data['title'] != "Unknown": score += 5
    if book_data.get('primary_author') and book_data['primary_author'] != "Unknown": score += 5

    # ML Confidence weighting
    locations = [e for e in comprehend_entities if e['Type'] == 'LOCATION' and e['Score'] > 0.8]
    orgs = [e for e in comprehend_entities if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.8]

    if locations: score += 10
    if orgs: score += 10

    # Data Richness
    if len(book_data.get('author_bio', '')) > 100: score += 10

    # External APIs
    if book_data.get('google_books_available'): score += 10
    if book_data.get('open_library_available'): score += 5

    return min(score, 100)

def lambda_handler(event, context):
    """
    Step Functions passes the ISBN in the event.
    Example event: { "isbn": "9780143193982", "jobId": "12345" }
    """
    isbn = event.get('isbn')
    job_id = event.get('jobId', 'unknown-job')

    if not isbn:
        return {"error": "Missing ISBN"}

    # 1. Fetch from Data Sources
    google_data = fetch_google_books(isbn)
    open_lib_data = fetch_open_library(isbn)
    biblio_data = fetch_biblioshare(isbn)

    # 2. Base mapping
    book_record = {
        "isbn_13": isbn,
        "job_id": job_id,
        "title": google_data.get('title') if google_data else "Unknown",
        "primary_author": google_data.get('authors', ["Unknown"])[0] if google_data else "Unknown",
        "author_bio": biblio_data.get('bio', ''),
        "author_location_raw": "",
        "author_institution": "",
        "google_books_available": bool(google_data),
        "open_library_available": bool(open_lib_data),
        "enrichment_date": datetime.now().strftime("%Y-%m-%d"),
        "enrichment_status": "Complete"
    }

    # 3. Amazon Comprehend Processing (Extracting Location & Organization)
    comprehend_entities = []
    if book_record['author_bio']:
        try:
            # THIS is where Amazon Comprehend reads the bio text to find entities
            response = comprehend.detect_entities(
                Text=book_record['author_bio'][:4900], # AWS Comprehend limit is 5000 bytes
                LanguageCode='en'
            )
            comprehend_entities = response.get('Entities', [])

            # Filter the ML results to grab high-confidence Locations and Organizations
            locations = [e['Text'] for e in comprehend_entities if e['Type'] == 'LOCATION' and e['Score'] > 0.8]
            orgs = [e['Text'] for e in comprehend_entities if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.8]

            # Save the first found Location and Org to our JSON
            book_record['author_location_raw'] = locations[0] if locations else ""
            book_record['author_institution'] = orgs[0] if orgs else ""
        except Exception as e:
            print(f"Comprehend Error: {e}")

    # 4. Calculate Confidence & Data Richness
    confidence_score = calculate_confidence(book_record, comprehend_entities)
    book_record['confidence_score'] = confidence_score

    if confidence_score >= 75:
        book_record['data_richness'] = 'Rich'
    elif confidence_score >= 50:
        book_record['data_richness'] = 'Moderate'
    else:
        book_record['data_richness'] = 'Basic'

    # Return the enriched row for this specific ISBN
    
    return book_record