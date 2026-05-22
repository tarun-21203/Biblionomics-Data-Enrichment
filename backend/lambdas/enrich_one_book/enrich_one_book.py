import boto3
import requests
import os
import uuid
import re
import time
import html as html_lib
import xml.etree.ElementTree as ET
from datetime import datetime

from config import (
    BISAC_TO_INDUSTRY, BISAC_INDUSTRY_DEFAULT,
    PUBLISHER_REGION_PATTERNS,
    PROVINCE_ABBREV_TO_FULL, PROVINCE_TO_REGION, CITY_TO_PROVINCE,
    BISAC_CODE_TO_HEADING, FLAGGED_BISAC_PREFIXES,
    LOCATION_SIGNAL_VERBS, REGION_DISPLAY_LABELS,
    PROFESSION_MODIFIERS, AWARD_PATTERNS,
    CSV_FIELD_NAMES,
    BIBLIOSHARE_ENDPOINT, GOOGLE_BOOKS_ENDPOINT, OPEN_LIBRARY_ENDPOINT,
    MAX_RETRIES, RETRY_BACKOFF_FACTOR,
)

comprehend = boto3.client('comprehend')

# ── ONIX Code → Human-Readable Maps ──────────────────────────────────────────
FORM_MAP = {
    'BB': 'Hardcover', 'BA': 'Hardcover', 'BC': 'Paperback',
    'BG': 'Spiral Bound', 'BH': 'Loose-leaf', 'BF': 'Bound Sheets',
    'DG': 'eBook', 'DA': 'eBook', 'AJ': 'Audiobook', 'AI': 'Audiobook',
}
FORM_DETAIL_MAP = {
    'B401': 'Jacketed',        'B402': 'Loose Jacket',    'B403': 'Laminated',
    'B406': 'With Dust Jacket','B407': 'Concealed Lamination',
    'B304': 'Trade Paperback', 'B302': 'Mass Market Paperback',
    'B501': 'Sewn',            'B502': 'Perfect Bound',   'B503': 'Library Binding',
    'B504': 'Spiral Bound',    'B601': 'Deckle Edge',     'B610': 'Gilt Edges',
    'B704': 'Pop-up',
}
AUDIENCE_MAP = {
    '01': 'General/Trade',     '02': 'Children',          '03': 'Young Adult',
    '04': 'Primary Education', '05': 'Secondary Education',
    '06': 'Higher Education',  '07': 'Professional/Academic',
}

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

def strip_html(text):
    """Decode HTML entities, remove tags, collapse whitespace."""
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


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


def isbn13_to_isbn10(isbn13):
    """Compute ISBN-10 via Mod-11 from a 978-prefix ISBN-13."""
    if not isbn13 or len(isbn13) != 13 or not isbn13.startswith('978'):
        return ""
    core  = isbn13[3:12]
    check = sum((i + 1) * int(d) for i, d in enumerate(core)) % 11
    return core + ('X' if check == 10 else str(check))


# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_google_books(isbn):
    try:
        res = fetch_with_retry(f"{GOOGLE_BOOKS_ENDPOINT}?q=isbn:{isbn}")
        if res:
            data = res.json()
            if 'items' in data:
                return data['items'][0]['volumeInfo']
    except Exception as e:
        print(f"Google Books Error: {e}")
    return None


def fetch_open_library(isbn):
    try:
        res = fetch_with_retry(OPEN_LIBRARY_ENDPOINT.format(isbn=isbn))
        if res:
            return res.json()


    except Exception as e:
        print(f"Open Library Error: {e}")
    return None


def fetch_biblioshare(isbn):
    """Fetch and fully parse ONIX 2.1 / 3.0 from BiblioShare."""


    token = os.environ.get('BIBLIOSHARE_TOKEN')
    if not token:
        print("Missing BIBLIOSHARE_TOKEN.")
        return {}

    try:
        res = fetch_with_retry(
            f"{BIBLIOSHARE_ENDPOINT}?Token={token}&EAN={isbn}", timeout=8
        )
        if not res:
            return {}

        root = ET.fromstring(res.content)
        
        # Check for error responses
        message_text = root.find(".//MessageText")
        if message_text is not None and message_text.text:
            error_msg = message_text.text.strip()
            print(f"BiblioShare error for ISBN {isbn}: {error_msg}")
            return {}
        
        d = {}

        def ft(*tags, parent=None):
            """Return first non-empty text found across tag variants."""
            node = parent if parent is not None else root
            for tag in tags:
                el = node.find(f".//{tag}")
                if el is not None and el.text and el.text.strip():
                    return el.text.strip()
            return ""

        # ── Identifiers ───────────────────────────────────────────────────────
        for pid in root.iter('ProductIdentifier'):
            ptype = ft('ProductIDType', 'b221', parent=pid)
            val   = ft('IDValue',       'b244', parent=pid)
            if ptype == '02':   d['isbn_10'] = val
            elif ptype == '03': d['isbn_13'] = val

        # ── Contributors & Bio ────────────────────────────────────────────────
        contributors, bio_raw = [], ""
        for contrib in root.iter('Contributor'):
            role    = ft('ContributorRole', 'b035', parent=contrib)
            name    = ft('PersonName', 'b036', 'PersonNameInverted', 'b037',
                         'CorporateName', 'b047', parent=contrib)
            country = ft('CountryCode', 'b251', parent=contrib)
            if name:
                contributors.append({'name': name, 'role': role, 'country': country})
            if not bio_raw:
                b = ft('BiographicalNote', 'b044', parent=contrib)
                if b:
                    bio_raw = b
        d['contributors'] = contributors
        d['bio']          = bio_raw
        d['cdn_creator']  = 'TRUE' if any(c.get('country') == 'CA' for c in contributors) else 'FALSE'

        # ── Title / Subtitle ──────────────────────────────────────────────────
        d['title']    = ft('TitleText', 'b203', 'DistinctiveTitle')
        d['subtitle'] = ft('Subtitle', 'b029')

        # ── Series ────────────────────────────────────────────────────────────
        d['series_title']  = ft('TitleOfSeries', 'b018')
        d['series_number'] = ft('NumberWithinSeries', 'b019')
        d['volume_number'] = ft('VolumeNumber', 'b033')

        # ── Publisher / Publication Date ──────────────────────────────────────
        d['publisher'] = ft('PublisherName', 'b081')
        pub_raw = ft('PublicationDate', 'b003')
        if pub_raw and len(pub_raw) == 8 and pub_raw.isdigit():
            d['publication_date'] = f"{pub_raw[:4]}-{pub_raw[4:6]}-{pub_raw[6:]}"
        else:
            d['publication_date'] = pub_raw

        # ── Product Form ──────────────────────────────────────────────────────
        pf          = ft('ProductForm', 'b012')
        pfd         = ft('ProductFormDetail', 'b333')
        form_name   = FORM_MAP.get(pf, pf or "")
        form_detail = FORM_DETAIL_MAP.get(pfd, "")   # blank if unrecognised code
        d['product_form']  = pf
        d['book_format']   = f"{form_name}, {form_detail}".strip(', ') if form_detail else form_name
        d['format_simple'] = form_name

        # ── Target Audience ───────────────────────────────────────────────────
        d['target_audience'] = AUDIENCE_MAP.get(ft('AudienceCode', 'b073'), 'General/Trade')

        # ── Descriptions ─────────────────────────────────────────────────────
        # ONIX 2.1 TextTypeCode: 01=main, 02=long, 04=TOC
        # ONIX 3.0 TextType:     02=short, 03=long, 08=TOC
        short_raw, long_raw, toc_raw = "", "", ""
        for ot in root.iter('OtherText'):
            code = ft('TextTypeCode', 'd102', parent=ot)
            text = ft('Text', 'd104', parent=ot)
            if code == '01' and not short_raw: short_raw = text
            elif code in ('02', '03') and not long_raw: long_raw = text
            elif code == '04' and not toc_raw: toc_raw = text
        for tc in root.iter('TextContent'):
            code = ft('TextType', 'x426', parent=tc)
            text = ft('Text', 'd104', parent=tc)
            if code == '02' and not short_raw: short_raw = text
            elif code in ('03', '04') and not long_raw: long_raw = text
            elif code == '08' and not toc_raw: toc_raw = text
        # If only a single long text came through under the 'short' slot, re-assign
        if short_raw and not long_raw and len(short_raw) > 400:
            long_raw, short_raw = short_raw, ""
        d['short_description'] = short_raw
        d['long_description']  = long_raw
        d['table_of_contents'] = toc_raw

        # ── Page Count ────────────────────────────────────────────────────────
        for ext in root.iter('Extent'):
            etype = ft('ExtentType', 'b218', parent=ext)
            eval_ = ft('ExtentValue', 'b219', parent=ext)
            if etype in ('00', '11') and eval_.isdigit():
                d['page_count'] = int(eval_)
                break

        # ── Dimensions / Weight ───────────────────────────────────────────────
        dims = {}
        for meas in root.iter('Measure'):
            mtype = ft('MeasureType', 'MeasureTypeCode', 'c093', parent=meas)
            mval  = ft('Measurement', 'c094', parent=meas)
            munit = (ft('MeasureUnitCode', 'c095', parent=meas) or '').lower()
            try:
                v = float(mval)
            except (ValueError, TypeError):
                continue

            # Normalise to both mm and inches
            if munit in ('mm', '01'):
                mm_v, in_v = round(v), round(v / 25.4, 1)
            elif munit == 'cm':
                mm_v, in_v = round(v * 10), round(v / 2.54, 1)
            elif munit in ('in', '02'):
                in_v, mm_v = round(v, 1), round(v * 25.4)
            elif munit in ('oz', '03') and mtype == '08':
                dims.update(weight_g=round(v * 28.35), weight_lb=round(v / 16, 2)); continue
            elif munit in ('lb', '04') and mtype == '08':
                dims.update(weight_g=round(v * 453.592), weight_lb=round(v, 2)); continue
            elif munit in ('gr', 'g', '05') and mtype == '08':
                dims.update(weight_g=round(v), weight_lb=round(v / 453.592, 2)); continue
            else:
                mm_v, in_v = round(v), round(v / 25.4, 1)

            if   mtype in ('01',): dims.update(height_mm=mm_v,    height_in=in_v)
            elif mtype in ('02',): dims.update(width_mm=mm_v,     width_in=in_v)
            elif mtype in ('03',): dims.update(thickness_mm=mm_v, thickness_in=in_v)
        d['dimensions'] = dims

        # ── BISAC Subjects — stored as ordered (code, heading) pairs ──────────
        subj_pairs = []
        for ms in root.iter('BASICMainSubject'):
            if ms.text:
                c = ms.text.strip()
                subj_pairs.insert(0, (c, BISAC_CODE_TO_HEADING.get(c, '')))
        for subj in root.iter('Subject'):
            scheme = ft('SubjectSchemeIdentifier', 'b067', 'x425', parent=subj)
            if scheme in ('10', '12'):
                c = ft('SubjectCode', 'b069', parent=subj)
                h = ft('SubjectHeadingText', 'b070', parent=subj)
                if c and not any(p[0] == c for p in subj_pairs):
                    subj_pairs.append((c, h or BISAC_CODE_TO_HEADING.get(c, '')))
        d['bisac_pairs'] = subj_pairs

        # ── Awards ────────────────────────────────────────────────────────────
        d['awards'] = "; ".join(
            ft('PrizeName', 'g126', parent=p)
            for p in root.iter('Prize')
            if ft('PrizeName', 'g126', parent=p)
        )

        # ── Pricing ───────────────────────────────────────────────────────────
        prices = {}
        for price in root.iter('Price'):
            currency = ft('CurrencyCode', 'j152', parent=price)
            amount   = ft('PriceAmount',  'j151', parent=price)
            try:
                prices[currency.upper()] = float(amount)
            except (ValueError, AttributeError):
                pass
        d['prices'] = prices

        # ── Cover Image ───────────────────────────────────────────────────────
        cover_url = ""
        for mf in root.iter('MediaFile'):
            if ft('MediaFileTypeCode', 'f114', parent=mf) in ('04', '03'):
                cover_url = ft('MediaFileLink', 'f116', parent=mf)
                if cover_url: break
        if not cover_url:
            for sr in root.iter('SupportingResource'):
                if ft('ResourceContentType', parent=sr) == '01':
                    rv = sr.find('.//ResourceVersion')
                    if rv is not None:
                        cover_url = ft('ResourceLink', parent=rv)
                        if cover_url: break
        d['cover_url'] = cover_url

        return d

    except Exception as e:
        print(f"BiblioShare Error: {e}")
        return {}


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


def resolve_institution(bio_clean, comprehend_orgs):
    """
    Return the author's primary institution.
    Prefers context-matched orgs (founder of X / serves at X) over bare NER,
    and excludes known media organisations.
    """
    for m in AFFILIATION_RE.finditer(bio_clean):
        candidate = m.group(1).strip().rstrip('.,;')
        if len(candidate) > 3:
            return candidate
    for org in comprehend_orgs:
        if org.lower() not in MEDIA_ORG_DENYLIST:
            return org
    return comprehend_orgs[0] if comprehend_orgs else ""


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
    if book.get('title')          and book['title']          != "Unknown": score += 5
    if book.get('primary_author') and book['primary_author'] != "Unknown": score += 5
    locs = [e for e in entities if e['Type'] == 'LOCATION'     and e['Score'] > 0.8]
    orgs = [e for e in entities if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.8]
    if locs: score += 10
    if orgs: score += 10
    if len(book.get('author_description', '')) > 100: score += 10
    if book.get('google_books_available') == "TRUE":  score += 10
    if book.get('open_library_available') == "TRUE":  score += 5
    if book.get('bisac_primary_code'):                score += 5
    return min(score, 100)


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
    biblio        = fetch_biblioshare(isbn)

    # ── 2. ISBN-10 ────────────────────────────────────────────────────────────
    isbn_10 = biblio.get('isbn_10') or isbn13_to_isbn10(isbn)

    # ── 3. Authors ────────────────────────────────────────────────────────────
    b_contributors = [
        c['name'] for c in biblio.get('contributors', [])
        if c.get('role') in ('A01', 'A12', 'A13', 'author', '')
    ]
    g_authors        = google_data.get('authors', []) if google_data else []
    author_pool      = b_contributors or g_authors
    primary_author   = author_pool[0] if author_pool else "Unknown"
    secondary_author = (author_pool[1] if len(author_pool) > 1
                        else g_authors[1] if len(g_authors) > 1 else "")
    all_authors      = "; ".join(dict.fromkeys(author_pool)) if author_pool else primary_author

    # ── 4. Strip HTML from all text fields before any further use ─────────────
    bio_clean   = strip_html(biblio.get('bio', ''))
    short_clean = strip_html(biblio.get('short_description', '')) or strip_html(
                  google_data.get('description', '')[:300] if google_data else '')
    long_clean  = strip_html(biblio.get('long_description', '')) or strip_html(
                  google_data.get('description', '') if google_data else '')
    toc_clean   = strip_html(biblio.get('table_of_contents', ''))

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

    # ── 12. Amazon Comprehend NLP (on clean text only) ────────────────────────
    comprehend_entities   = []
    author_location_raw   = ""
    author_institution    = ""
    author_profession_raw = ""
    locations_mentioned   = ""
    time_period_mentioned = ""

    if bio_clean:
        try:
            bio_ents            = comprehend.detect_entities(Text=bio_clean[:4900], LanguageCode='en').get('Entities', [])
            comprehend_entities = bio_ents
            bio_locs  = [e['Text'] for e in bio_ents if e['Type'] == 'LOCATION'     and e['Score'] > 0.8]
            bio_orgs  = [e['Text'] for e in bio_ents if e['Type'] == 'ORGANIZATION' and e['Score'] > 0.8]
            bio_dates = [e['Text'] for e in bio_ents if e['Type'] == 'DATE'         and e['Score'] > 0.8]

            author_location_raw = bio_locs[0] if bio_locs else ""
            author_institution  = resolve_institution(bio_clean, bio_orgs)

            if bio_dates:
                years = sorted(set(
                    m.group(0) for d in bio_dates
                    for m in [re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', d)] if m
                ))
                time_period_mentioned = f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "")

            kp_resp = comprehend.detect_key_phrases(Text=bio_clean[:4900], LanguageCode='en')
            prof_phrases = [
                p['Text'] for p in kp_resp.get('KeyPhrases', [])
                if p['Score'] > 0.8
                and any(kw in p['Text'].lower() for kw in PROFESSION_KEYWORDS)
            ]
            author_profession_raw = prof_phrases[0] if prof_phrases else ""

        except Exception as e:
            print(f"Comprehend (bio) Error: {e}")

    # Locations across full text (bio + description combined)
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
    record['verification_status'] = 'Verified' if cs >= 75 else 'Unverified'
    record['fields_populated']    = count_populated(record)

    # ── 18. Return in canonical CSV spec order ────────────────────────────────
    return {k: record.get(k) for k in CSV_FIELD_NAMES}