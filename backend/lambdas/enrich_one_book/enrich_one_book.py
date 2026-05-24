import boto3
import os
import uuid
import re
from datetime import datetime

# Import modular components
from api_clients import fetch_biblioshare, fetch_google_books, fetch_open_library
from onix_parser import parse_onix
from html_utils import clean_html

from config import (
    BISAC_TO_INDUSTRY, BISAC_INDUSTRY_DEFAULT,
    PUBLISHER_REGION_PATTERNS,
    PROVINCE_ABBREV_TO_FULL, PROVINCE_TO_REGION, CITY_TO_PROVINCE,
    BISAC_CODE_TO_HEADING, FLAGGED_BISAC_PREFIXES,
    LOCATION_SIGNAL_VERBS, REGION_DISPLAY_LABELS,
    PROFESSION_MODIFIERS, AWARD_PATTERNS,
    CSV_FIELD_NAMES,
)

comprehend = boto3.client('comprehend')


# ── US location keywords (catch-all for non-Canadian locations) ───────────────
US_LOCATION_KEYWORDS = {
    'new york', 'los angeles', 'chicago', 'houston', 'dallas', 'atlanta',
    'boston', 'seattle', 'miami', 'washington', 'nashville', 'san francisco',
    'philadelphia', 'phoenix', 'denver', 'portland', 'california', 'texas',
    'florida', 'illinois', 'georgia', 'united states', 'usa', 'u.s.',
}

# ── Media organizations — excluded from author_institution ───────────────────
MEDIA_ORG_DENYLIST = {
    'new york times', 'washington post', 'cnn', 'bbc', 'nbc', 'abc', 'cbs',
    'fox news', 'guardian', 'huffpost', 'forbes', 'time', 'newsweek',
    'bloomberg', 'reuters', 'associated press', 'usa today',
    'wall street journal', 'wsj', 'new yorker', 'vanity fair',
    'people', 'time100',
}

# ── Author affiliation context regex ─────────────────────────────────────────
AFFILIATION_RE = re.compile(
    r'(?:founder\s+of|co-founder\s+of|serves?\s+(?:as\s+\w+\s+)?at|'
    r'works?\s+(?:at|for|with)|director\s+of|based\s+at|'
    r'faculty\s+(?:at|of)|professor\s+(?:at|of)|pastor\s+(?:at|of)|'
    r'appointed\s+(?:\w+\s+)?(?:at|of|to))\s+(?:the\s+)?([A-Z][^.,;\n]{2,60})',
    re.IGNORECASE,
)

PROFESSION_KEYWORDS = [
    'author', 'speaker', 'founder', 'co-founder', 'pastor', 'professor',
    'director', 'executive', 'entrepreneur', 'journalist', 'writer',
    'editor', 'researcher', 'scientist', 'doctor', 'lawyer', 'coach',
    'consultant', 'philanthropist', 'activist', 'minister', 'reverend',
    'theologian', 'curator', 'designer', 'architect', 'photographer',
    'producer', 'broadcaster',
]


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────


def isbn13_to_isbn10(isbn13):
    """Compute ISBN-10 via Mod-11 from a 978-prefix ISBN-13."""
    if not isbn13 or len(isbn13) != 13 or not isbn13.startswith('978'):
        return ""
    core  = isbn13[3:12]
    check = sum((i + 1) * int(d) for i, d in enumerate(core)) % 11
    return core + ('X' if check == 10 else str(check))

# ─────────────────────────────────────────────────────────────────────────────
# ENRICHMENT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def bisac_levels(bisac_pairs):
    """
    Derive (L1, L2, L3, L4) from ordered (code, heading) pairs.
    Primary code → config BISAC_CODE_TO_HEADING lookup wins over raw ONIX text.
    """
    for code, heading in bisac_pairs:
        resolved = BISAC_CODE_TO_HEADING.get(code) or heading
        if resolved:
            parts = [p.strip() for p in resolved.split('/')]
            return tuple((parts[i] if i < len(parts) else '') for i in range(4))
    return ('', '', '', '')


def resolve_publisher_region(pub_name):
    if not pub_name:
        return "USA"
    low = pub_name.lower()
    for patterns, region in PUBLISHER_REGION_PATTERNS:
        if any(p.lower() in low for p in patterns):
            return region
    return "USA"


def resolve_author_location(location_raw):
    """Return (province_or_country, region) from a raw location string."""
    if not location_raw:
        return "", ""
    low = location_raw.lower().strip()

    for city, province in CITY_TO_PROVINCE.items():      # Canadian cities
        if city.lower() in low:
            return province, PROVINCE_TO_REGION.get(province, "Canada")

    if low.upper() in PROVINCE_ABBREV_TO_FULL:            # Province abbrev
        prov = PROVINCE_ABBREV_TO_FULL[low.upper()]
        return prov, PROVINCE_TO_REGION.get(prov, "Canada")

    for prov in PROVINCE_TO_REGION:                       # Province full name
        if prov.lower() in low:
            return prov, PROVINCE_TO_REGION[prov]

    if 'canada' in low:
        return "Canada", "Canada"

    if any(kw in low for kw in US_LOCATION_KEYWORDS):     # US locations
        return "USA", "USA"

    return "International", "International"


def is_corporate_appropriate(bisac_codes):
    for code in bisac_codes:
        if any(code.startswith(pref) for pref in FLAGGED_BISAC_PREFIXES):
            return "FALSE"
    return "TRUE"


def classify_size(h_mm, w_mm):
    if not h_mm or not w_mm: return "Unknown"
    a = h_mm * w_mm
    return "Large" if a > 60000 else "Standard" if a > 35000 else "Compact"


def classify_length(pages):
    if not pages or pages == 0: return "Unknown"
    return "Short" if pages < 100 else "Long" if pages > 400 else "Standard"


def classify_gift_tier(usd):
    if not usd: return "Unknown"
    return "Luxury" if usd >= 35 else "Premium" if usd >= 25 else "Mid-Range" if usd >= 15 else "Budget"


def clean_profession(raw):
    """Strip adjectival modifiers and leading articles from a profession phrase."""
    if not raw:
        return raw
    words   = raw.split()
    cleaned = [w for w in words if w.lower().strip('.,') not in PROFESSION_MODIFIERS]
    result  = re.sub(r'^(?:a|an|the)\s+', '', " ".join(cleaned), flags=re.IGNORECASE)
    return result.strip()


def extract_awards_from_text(text):
    """Use AWARD_PATTERNS from config to mine award mentions out of free text."""
    if not text:
        return ""
    found = []
    for pattern in AWARD_PATTERNS:
        for m in re.finditer(pattern, text):
            award = m.group(1).strip().rstrip('.,;')
            if len(award) > 4 and award not in found:
                found.append(award)
    return "; ".join(found[:5])


def build_author_summary(name, region, profession_raw, institution):
    """Construct a one-line author summary using REGION_DISPLAY_LABELS."""
    if not name or name == "Unknown":
        return ""
    parts = [f"{name} is"]
    display_region = REGION_DISPLAY_LABELS.get(region, region)
    if display_region:
        pfx = "an" if display_region[0].lower() in "aeiou" else "a"
        parts.append(f"{pfx} {display_region}-based")
    profession = clean_profession(profession_raw)
    if profession:
        parts.append(profession)
    if institution:
        parts.append(f"at {institution}")
    return " ".join(parts)


def extract_extras(bio, entities):
    """Mine bio for unverified works, roles, and affiliations."""
    if not bio:
        return ""
    lines = []

    for m in re.findall(r'(?:author of|co-author of|wrote)\s+([A-Z][^.,;]{5,60})', bio):
        lines.append(f"[UNVERIFIED] Other works: {m.strip()}")

    ROLE_STOP = {'a','an','the','his','her','their','its','at','in','of','and','as'}
    for m in re.finditer(
        r'(?:serves?\s+as|is\s+the|as\s+(?:an?\s+)?|appointed\s+(?:as\s+)?)'
        r'([A-Za-z][A-Za-z\s]{3,40})',
        bio, re.IGNORECASE,
    ):
        words = m.group(1).strip().split()
        while words and words[-1].lower() in ROLE_STOP:
            words.pop()
        role = " ".join(words)
        if role and len(role) > 3:
            lines.append(f"[UNVERIFIED] Role: {role}")

    seen, result = set(), []
    for line in lines:
        if line not in seen:
            seen.add(line)
            result.append(line)
    return "\n".join(result[:6])


def calc_confidence(book, entities):
    score = 30
    
    if book.get('title') and book['title'] != "Unknown": 
        score += 5
    
    if book.get('primary_author') and book['primary_author'] != "Unknown": 
        score += 5
    
    # FIXED: Lower confidence threshold to match spaCy behavior (0.7 instead of 0.8)
    locs = [e for e in entities if e['Type'] == 'LOCATION' and e['Score'] > 0.7]
    orgs = [e for e in entities if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.7]
    
    # ENHANCED: Award points for successful location extraction via any method
    if locs or book.get('author_location_raw'): 
        score += 10
    
    if orgs: 
        score += 10
    
    if len(book.get('author_description', '')) > 100: 
        score += 10
    
    if book.get('google_books_available') == "TRUE": 
        score += 10
    
    if book.get('open_library_available') == "TRUE": 
        score += 5
    
    if book.get('bisac_primary_code'): 
        score += 5
    
    final_score = min(score, 100)
    return final_score


def count_populated(record):
    return sum(
        1 for k, v in record.items()
        if k != 'fields_populated'
        and v is not None and v != "" and v != "Unknown"
    )


# ─────────────────────────────────────────────────────────────────────────────
# LAMBDA HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    isbn   = event.get('isbn')
    job_id = event.get('jobId', 'unknown-job')
    if not isbn:
        return {"error": "Missing ISBN"}

    # ── 1. Fetch sources ──────────────────────────────────────────────────────
    google_data   = fetch_google_books(isbn)
    open_lib_data = fetch_open_library(isbn)
    
    # Fetch and parse BiblioShare ONIX XML
    biblio_xml = fetch_biblioshare(isbn)
    if biblio_xml and not isinstance(biblio_xml, dict):
        # Parse ONIX XML into dict
        biblio = parse_onix(biblio_xml)
        # Check for parse errors
        if '_parse_error' in biblio:
            print(f"ONIX parse error for {isbn}: {biblio['_parse_error']}")
            biblio = {}
    else:
        biblio = {}

    # ── 2. ISBN-10 ────────────────────────────────────────────────────────────
    isbn_10 = biblio.get('isbn_10') or isbn13_to_isbn10(isbn)

    # ── 3. Authors (WITH SEQUENCENUMBER SORTING from parse_onix) ─────────────
    b_contributors = [
        c['name'] for c in biblio.get('contributors', [])
        if c.get('role') in ('A01', 'A12', 'A13', 'A02', 'author', '')
    ]
    g_authors        = google_data.get('authors', []) if google_data else []
    author_pool      = b_contributors or g_authors
    primary_author   = author_pool[0] if author_pool else "Unknown"
    secondary_author = (author_pool[1] if len(author_pool) > 1
                        else g_authors[1] if len(g_authors) > 1 else "")
    all_authors      = "; ".join(dict.fromkeys(author_pool)) if author_pool else primary_author

    # ── 4. Get text fields (already cleaned by onix_parser) ──────────────────
    # Note: onix_parser.py already uses clean_html() on all HTML fields,
    bio_clean   = biblio.get('bio', '')
    short_clean = biblio.get('short_description', '') or clean_html(
                  google_data.get('description', '')[:300] if google_data else '')
    long_clean  = biblio.get('long_description', '') or clean_html(
                  google_data.get('description', '') if google_data else '')
    toc_clean   = biblio.get('table_of_contents', '')

    # ── 5. Bibliographic metadata ─────────────────────────────────────────────
    title           = biblio.get('title') or (google_data.get('title') if google_data else '') or 'Unknown'
    subtitle        = biblio.get('subtitle') or (google_data.get('subtitle', '') if google_data else '')
    publisher       = biblio.get('publisher') or (google_data.get('publisher', '') if google_data else '')
    pub_date        = biblio.get('publication_date') or (google_data.get('publishedDate', '') if google_data else '')
    page_count      = biblio.get('page_count') or (google_data.get('pageCount') if google_data else None)
    awards_onix     = biblio.get('awards', '')
    series_title    = biblio.get('series_title', '')
    series_number   = biblio.get('series_number', '')
    volume_number   = biblio.get('volume_number', '')
    target_audience = biblio.get('target_audience', 'General/Trade')
    book_format     = biblio.get('book_format', '')
    format_simple   = biblio.get('format_simple', book_format.split(',')[0].strip() if book_format else '')
    cdn_creator     = biblio.get('cdn_creator', 'FALSE')

    # ── 6. Cover ──────────────────────────────────────────────────────────────
    cover_source = biblio.get('cover_url', '')
    if not cover_source and google_data:
        imgs = google_data.get('imageLinks', {})
        cover_source = imgs.get('extraLarge') or imgs.get('large') or imgs.get('thumbnail', '')

    # ── 7. Dimensions ─────────────────────────────────────────────────────────
    dims         = biblio.get('dimensions', {})
    height_mm    = dims.get('height_mm');    height_in    = dims.get('height_in')
    width_mm     = dims.get('width_mm');     width_in     = dims.get('width_in')
    thickness_mm = dims.get('thickness_mm'); thickness_in = dims.get('thickness_in')
    weight_g     = dims.get('weight_g');     weight_lb    = dims.get('weight_lb')
    cover_dims   = f"{height_in} x {width_in}" if height_in and width_in else ""

    # ── 8. BISAC — primary code drives all level fields ───────────────────────
    bisac_pairs          = biblio.get('bisac_pairs', [])
    bisac_codes          = [p[0] for p in bisac_pairs]
    bisac_primary_code   = bisac_codes[0] if len(bisac_codes) > 0 else ''
    bisac_secondary_code = bisac_codes[1] if len(bisac_codes) > 1 else ''
    bisac_tertiary_code  = bisac_codes[2] if len(bisac_codes) > 2 else ''

    l1, l2, l3, l4 = bisac_levels(bisac_pairs)
    if not l1 and google_data:                             # Google Books fallback
        cats = google_data.get('categories', [])
        if cats:
            parts = [p.strip() for p in cats[0].split('/')]
            l1 = parts[0] if parts else ''
            l2 = parts[1] if len(parts) > 1 else ''

    genre_tags        = l1
    book_themes_bisac = " / ".join(p for p in [l1, l2, l3] if p)
    corp_appropriate  = is_corporate_appropriate(bisac_codes) if bisac_codes else "TRUE"

    # ── 9. Pricing ────────────────────────────────────────────────────────────
    prices         = biblio.get('prices', {})
    list_price_cad = prices.get('CAD')
    list_price_usd = prices.get('USD')

    # ── 10. Classification helpers ────────────────────────────────────────────
    book_size_category   = classify_size(height_mm, width_mm)
    book_length_category = classify_length(page_count)
    gift_price_tier      = classify_gift_tier(list_price_usd)
    pub_region           = resolve_publisher_region(publisher)
    primary_industry     = BISAC_TO_INDUSTRY.get(l1.upper() if l1 else '', BISAC_INDUSTRY_DEFAULT)

    # ── 11. Google Books extras ───────────────────────────────────────────────
    gb_rating       = google_data.get('averageRating')  if google_data else None
    gb_rating_count = google_data.get('ratingsCount')   if google_data else None
    reading_level   = "Adult" if google_data and google_data.get('maturityRating') == 'MATURE' else ""

    # ── 12. Amazon Comprehend NLP (adapted from biblioNomics spaCy approach) ──
    comprehend_entities   = []
    author_location_raw   = ""
    author_institution    = ""
    author_profession_raw = ""
    locations_mentioned   = ""
    time_period_mentioned = ""

    if bio_clean:
        try:
            
            # Get all entities from bio
            bio_ents = comprehend.detect_entities(Text=bio_clean[:4900], LanguageCode='en').get('Entities', [])
            comprehend_entities = bio_ents
            
            
            # Extract entities by type with confidence > 0.8
            bio_locs  = [(e['Text'], e['BeginOffset']) for e in bio_ents if e['Type'] == 'LOCATION' and e['Score'] > 0.8]
            bio_orgs  = [(e['Text'], e['BeginOffset']) for e in bio_ents if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.8]
            bio_dates = [e['Text'] for e in bio_ents if e['Type'] == 'DATE' and e['Score'] > 0.8]
            
            
            # ── LOCATION: Proximity-based scoring ────────────
            # Score locations by proximity to location-signal verbs
            if bio_locs:
                def score_location_by_proximity(loc_text, loc_offset):
                    """Score based on proximity to location signal verbs"""
                    min_dist = float('inf')
                    for verb in LOCATION_SIGNAL_VERBS:
                        # Find position of signal verb in bio
                        pos = bio_clean.lower().find(verb)
                        if pos != -1:
                            dist = abs(loc_offset - pos)
                            min_dist = min(min_dist, dist)
                            print(f"DEBUG NLP: Found signal verb '{verb}' at pos {pos}, distance to '{loc_text}' at {loc_offset}: {dist}")
                    return min_dist
                
                # Sort by proximity score (lower = better)
                scored_locs = [(loc, score_location_by_proximity(loc, offset)) for loc, offset in bio_locs]
                scored_locs.sort(key=lambda x: x[1])
                author_location_raw = scored_locs[0][0]

            
            # ── INSTITUTION: Context-aware extraction ─────────
            # Look for ORGs linked to affiliation contexts
            if not author_institution and bio_orgs:
                # Try regex patterns first (founder of, works at, serves at, etc.)
                for m in AFFILIATION_RE.finditer(bio_clean):
                    candidate = m.group(1).strip().rstrip('.,;')
                    if len(candidate) > 3:
                        author_institution = candidate
                        break
                
                # Fallback: use first ORG entity if no pattern match
                if not author_institution:
                    # Filter out media organizations
                    for org, _ in bio_orgs:
                        if org.lower() not in MEDIA_ORG_DENYLIST:
                            author_institution = org
                            break
                
                # Last resort: take first ORG even if it's media
                if not author_institution and bio_orgs:
                    author_institution = bio_orgs[0][0]
            
            # ── CITY-FROM-ORG fallback ────────────────────────
            # If no location found but institution exists, try to extract city from org name
            if not author_location_raw and author_institution:
                tokens = author_institution.split()
                for token in reversed(tokens):
                    cleaned = token.strip("'s,.")

                    if cleaned in CITY_TO_PROVINCE:
                        author_location_raw = cleaned
                        break
            
            # ── ADDITIONAL FALLBACK: Extract cities from ALL organization entities ──────
            # Even if we didn't use the org as institution, check all orgs for city names
            if not author_location_raw and bio_orgs:
                for org_text, _ in bio_orgs:
                    tokens = org_text.split()
                    for token in reversed(tokens):
                        cleaned = token.strip("'s,.")
                        
                        # Check Canadian cities
                        if cleaned in CITY_TO_PROVINCE:
                            author_location_raw = cleaned
                            break
                        
                        # Check US cities (like biblioNomics does)
                        us_cities = {
                            "New York", "Los Angeles", "Chicago", "Houston", "Dallas",
                            "Nashville", "Atlanta", "Boston", "San Francisco", "Seattle",
                            "Portland", "Denver", "Miami", "Philadelphia", "Phoenix",
                            "Detroit", "Minneapolis", "Austin", "Brooklyn", "Manhattan",
                            "Washington"
                        }
                        if cleaned in us_cities:
                            author_location_raw = cleaned
                            print(f"DEBUG NLP: Found US city '{cleaned}' in org name!")
                            break
                    
                    if author_location_raw:
                        break
            
            # ── REGEX FALLBACK: Direct text search for common city names ────────────────
            if not author_location_raw:
                # Search for city names directly in the text
                # Combine all city names for search
                all_cities = list(CITY_TO_PROVINCE.keys()) + [
                    "New York", "Los Angeles", "Chicago", "Houston", "Dallas",
                    "Nashville", "Atlanta", "Boston", "San Francisco", "Seattle",
                    "Portland", "Denver", "Miami", "Philadelphia", "Phoenix",
                    "Detroit", "Minneapolis", "Austin", "Brooklyn", "Manhattan",
                    "Washington"
                ]
                
                for city in all_cities:
                    # Look for city name as a word boundary
                    pattern = r'\b' + re.escape(city) + r'\b'
                    if re.search(pattern, bio_clean, re.IGNORECASE):
                        author_location_raw = city
                        break
            
            # ── PROFESSION: Key phrases + regex patterns ──────────────────────────
            # Use Comprehend key phrases instead of spaCy dependency parsing
            kp_resp = comprehend.detect_key_phrases(Text=bio_clean[:4900], LanguageCode='en')
            prof_phrases = []
            
            # Extract key phrases containing profession keywords
            for p in kp_resp.get('KeyPhrases', []):
                if p['Score'] > 0.8 and any(kw in p['Text'].lower() for kw in PROFESSION_KEYWORDS):
                    prof_phrases.append(p['Text'])
            
            # Also try regex patterns as fallback
            if not prof_phrases:
                patterns = [
                    r"(?:is|was) an? (.+?)(?:\.|She |He |They |,)",
                    r"award-winning (.+?)(?:\.|,|;| and | who )",
                    r"(\w+(?:\s\w+)*) and author\b",
                ]
                for pattern in patterns:
                    match = re.search(pattern, bio_clean, re.IGNORECASE)
                    if match:
                        prof_phrases.append(match.group(1).strip())
                        break
            
            # Split compound professions and clean
            if prof_phrases:
                all_professions = []
                for raw in prof_phrases:
                    # Split on comma + optional conjunction, or standalone conjunction
                    parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", raw)
                    for part in parts:
                        part = part.strip()
                        if part:
                            # Remove modifier words
                            words = part.split()
                            filtered = [w for w in words if w.lower().strip('.,') not in PROFESSION_MODIFIERS]
                            if filtered:
                                all_professions.append(" ".join(filtered))
                
                # Deduplicate and join
                seen = set()
                unique = []
                for p in all_professions:
                    p_lower = p.lower()
                    if p_lower not in seen and len(p) > 2:
                        seen.add(p_lower)
                        unique.append(p)
                
                author_profession_raw = ", ".join(unique[:3])  # Limit to 3 professions
            
            # ── TIME PERIODS ───────────────────────────────────────────────────────
            if bio_dates:
                years = sorted(set(
                    m.group(0) for d in bio_dates
                    for m in [re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', d)] if m
                ))
                time_period_mentioned = f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "")

        except Exception as e:
            print(f"Comprehend (bio) Error: {e}")

    # ── Locations across full text (bio + description combined) ───────────────
    combined = (bio_clean + " " + long_clean)[:4900]
    if combined.strip():
        try:
            all_ents = comprehend.detect_entities(Text=combined, LanguageCode='en').get('Entities', [])
            locs_all = list(dict.fromkeys(
                e['Text'] for e in all_ents if e['Type'] == 'LOCATION' and e['Score'] > 0.8
            ))
            locations_mentioned = ", ".join(locs_all)
        except Exception as e:
            print(f"Comprehend (combined) Error: {e}")

    # ── 13. Author derived fields ─────────────────────────────────────────────
    author_province, author_region = resolve_author_location(author_location_raw)
    bio_len             = len(bio_clean)
    author_bio_richness = "Rich" if bio_len > 300 else "Moderate" if bio_len > 100 else "Basic" if bio_len > 0 else "None"
    author_summary      = build_author_summary(primary_author, author_region, author_profession_raw, author_institution)

    # ── 14. Awards: ONIX first; fall back to pattern mining ───────────────────
    if not awards_onix:
        awards_onix = extract_awards_from_text(bio_clean + " " + long_clean)

    # ── 15. Data sources ──────────────────────────────────────────────────────
    data_sources = " | ".join(filter(None, [
        "BiblioShare" if biblio        else "",
        "Google Books" if google_data  else "",
        "Open Library" if open_lib_data else "",
    ]))

    # ── 16. Assemble flat record ──────────────────────────────────────────────
    record = {
        "id":                    str(uuid.uuid4()),
        "title":                 title,
        "primary_author":        primary_author,
        "isbn_13":               isbn,
        "book_format":           book_format,
        "cdn_creator":           cdn_creator,
        "short_description":     short_clean,
        "genre_tags":            genre_tags,
        "cover_source":          cover_source,
        "isbn_10":               isbn_10,
        "subtitle":              subtitle,
        "series_title":          series_title,
        "publisher":             publisher,
        "author_description":    bio_clean,
        "awards":                awards_onix,
        "bisac_primary_code":    bisac_primary_code,
        "bisac_secondary_code":  bisac_secondary_code,
        "bisac_tertiary_code":   bisac_tertiary_code,
        "bisac_level_1":         l1,
        "bisac_level_2":         l2,
        "bisac_level_3":         l3,
        "bisac_level_4":         l4,
        "series_number":         series_number,
        "volume_number":         volume_number,
        "table_of_contents":     toc_clean,
        "all_authors":           all_authors,
        "secondary_author":      secondary_author,
        "publication_date":      pub_date,
        "format":                format_simple,
        "long_description":      long_clean,
        "page_count":            page_count,
        "target_audience":       target_audience,
        "list_price_cad":        list_price_cad,
        "list_price_usd":        list_price_usd,
        "reading_level":         reading_level,
        "book_height_in":        height_in,
        "book_height_mm":        height_mm,
        "book_width_in":         width_in,
        "book_width_mm":         width_mm,
        "spine_thickness_in":    thickness_in,
        "spine_thickness_mm":    thickness_mm,
        "book_weight_lb":        weight_lb,
        "book_weight_g":         weight_g,
        "cover_dimensions":      cover_dims,
        "book_size_category":    book_size_category,
        "author_location_raw":   author_location_raw,
        "author_province":       author_province,
        "author_region":         author_region,
        "author_profession_raw": author_profession_raw,
        "author_institution":    author_institution,
        "author_bio_richness":   author_bio_richness,
        "author_summary":        author_summary,
        "primary_industry":      primary_industry,
        "gift_price_tier":       gift_price_tier,
        "book_length_category":  book_length_category,
        "publisher_region":      pub_region,
        "book_themes_bisac":     book_themes_bisac,
        "locations_mentioned":   locations_mentioned,
        "time_period_mentioned": time_period_mentioned,
        "corporate_appropriate": corp_appropriate,
        "google_books_rating":       gb_rating,
        "google_books_rating_count": gb_rating_count,
        "google_books_available":    "TRUE" if google_data   else "FALSE",
        "open_library_available":    "TRUE" if open_lib_data else "FALSE",
        "amazon_ca_url":    f"https://amazon.ca/dp/{isbn_10}" if isbn_10 else "",
        "goodreads_url":    f"https://goodreads.com/book/isbn/{isbn}",
        "enrichment_status": "Complete",
        "enrichment_date":   datetime.now().strftime("%Y-%m-%d"),
        "confidence_score":  0,     # resolved below
        "data_richness":     "",
        "data_sources":      data_sources,
        "fields_populated":  0,
        "verification_status": "",
        "last_updated":      datetime.now().strftime("%Y-%m-%d"),
        "extracted_extras":  extract_extras(bio_clean, comprehend_entities),
    }

    # ── 17. Scoring ───────────────────────────────────────────────────────────
    cs = calc_confidence(record, comprehend_entities)
    record['confidence_score']    = cs
    record['data_richness']       = 'Rich' if cs >= 75 else 'Moderate' if cs >= 50 else 'Basic'
    # FIXED: Lower verification threshold to match biblioNomics (70 instead of 75)
    record['verification_status'] = 'Verified' if cs >= 70 else 'Unverified'
    record['fields_populated']    = count_populated(record)

    # ── 18. Return in canonical CSV spec order 
    return {k: record.get(k) for k in CSV_FIELD_NAMES}