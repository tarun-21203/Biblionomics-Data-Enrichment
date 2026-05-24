"""
BIBLIOnomics Lambda — ONIX XML Parser
Parses BiblioShare ONIX XML responses into flat Python dicts.
Enhanced with robust HTML cleaning and SequenceNumber-based contributor sorting.
"""

import xml.etree.ElementTree as ET

from html_utils import clean_html
from config import BISAC_CODE_TO_HEADING


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


def _text(element):
    """Safely extract text content from an XML element."""
    if element is None:
        return ""
    return (element.text or "").strip()


def _clean_text(element):
    """
    Extract text from an XML element that may contain HTML markup.
    Use this instead of _text() for BiographicalNote, OtherText, etc.
    """
    if element is None:
        return ""
    raw = (element.text or "").strip()
    return clean_html(raw)


def _int(element):
    """Safely extract an int from an XML element."""
    t = _text(element)
    if not t:
        return None
    try:
        return int(float(t))
    except (ValueError, TypeError):
        return None


def _float(element):
    """Safely extract a float from an XML element."""
    t = _text(element)
    if not t:
        return None
    try:
        return float(t)
    except (ValueError, TypeError):
        return None


def _find_text(root, *tags, parent=None):
    """Return first non-empty text found across tag variants."""
    node = parent if parent is not None else root
    for tag in tags:
        el = node.find(f".//{tag}")
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _parse_bisac_heading(code, heading_text=None):
    """
    Parse BISAC levels from a heading string or code lookup.
    Priority 1: Use the code lookup table (structured, reliable)
    Priority 2: Use SubjectHeadingText if available and well-formed
    
    Enhanced to handle both " / " (with spaces) and "/" delimiters.
    """
    heading = None
    
    # Priority 1: Use the code lookup table
    if code:
        # Try full length, then 6-char prefix, then 3-char prefix
        for length in (len(code), 6, 3):
            if length > len(code):
                continue
            prefix = code[:length] + "0" * (len(code) - length)
            if prefix in BISAC_CODE_TO_HEADING:
                heading = BISAC_CODE_TO_HEADING[prefix]
                break
    
    # Priority 2: Use SubjectHeadingText if available and contains delimiter
    if heading_text:
        cleaned = clean_html(heading_text)
        if " / " in cleaned or "/" in cleaned:
            heading = cleaned
    
    if not heading:
        return {"level_1": "", "level_2": "", "level_3": "", "level_4": ""}
    
    # Normalize: split on " / " first, then fall back to "/"
    if " / " in heading:
        parts = [p.strip() for p in heading.split(" / ")]
    else:
        parts = [p.strip() for p in heading.split("/")]
    
    return {
        "level_1": parts[0] if len(parts) > 0 else "",
        "level_2": parts[1] if len(parts) > 1 else "",
        "level_3": parts[2] if len(parts) > 2 else "",
        "level_4": parts[3] if len(parts) > 3 else "",
    }


def _parse_pub_date(raw):
    """Convert YYYYMMDD or YYYYMM to ISO format."""
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) == 6 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}"
    return raw


def _parse_dimensions(root):
    """
    Extract physical dimensions from ONIX Measure elements.
    Handles both inches/mm and lb/gr units, converting as needed.
    """
    IN_TO_MM = 25.4
    LB_TO_G = 453.592
    
    dims = {}
    
    for meas in root.iter('Measure'):
        mtype = _find_text(root, 'MeasureType', 'MeasureTypeCode', 'c093', parent=meas)
        mval = _find_text(root, 'Measurement', 'c094', parent=meas)
        munit = (_find_text(root, 'MeasureUnitCode', 'c095', parent=meas) or '').lower()
        
        try:
            v = float(mval)
        except (ValueError, TypeError):
            continue
        
        # Height
        if mtype in ('01',):
            if munit in ('mm', '01'):
                dims['height_mm'] = round(v)
                dims['height_in'] = round(v / IN_TO_MM, 2)
            elif munit == 'cm':
                dims['height_mm'] = round(v * 10)
                dims['height_in'] = round(v / 2.54, 2)
            elif munit in ('in', '02'):
                dims['height_in'] = round(v, 2)
                dims['height_mm'] = round(v * IN_TO_MM)
        
        # Width
        elif mtype in ('02',):
            if munit in ('mm', '01'):
                dims['width_mm'] = round(v)
                dims['width_in'] = round(v / IN_TO_MM, 2)
            elif munit == 'cm':
                dims['width_mm'] = round(v * 10)
                dims['width_in'] = round(v / 2.54, 2)
            elif munit in ('in', '02'):
                dims['width_in'] = round(v, 2)
                dims['width_mm'] = round(v * IN_TO_MM)
        
        # Thickness
        elif mtype in ('03',):
            if munit in ('mm', '01'):
                dims['thickness_mm'] = round(v, 1)
                dims['thickness_in'] = round(v / IN_TO_MM, 2)
            elif munit == 'cm':
                dims['thickness_mm'] = round(v * 10, 1)
                dims['thickness_in'] = round(v / 2.54, 2)
            elif munit in ('in', '02'):
                dims['thickness_in'] = round(v, 2)
                dims['thickness_mm'] = round(v * IN_TO_MM, 1)
        
        # Weight
        elif mtype in ('08',):
            if munit in ('oz', '03'):
                dims['weight_g'] = round(v * 28.35)
                dims['weight_lb'] = round(v / 16, 3)
            elif munit in ('lb', '04'):
                dims['weight_lb'] = round(v, 3)
                dims['weight_g'] = round(v * LB_TO_G)
            elif munit in ('gr', 'g', '05'):
                dims['weight_g'] = round(v)
                dims['weight_lb'] = round(v / LB_TO_G, 3)
    
    return dims


def parse_onix(xml_content):
    """
    Parse BiblioShare ONIX XML response into a flat dict.
    
    Enhanced features:
    - Uses clean_html() with BeautifulSoup for robust HTML entity handling
    - Sorts contributors by SequenceNumber for proper primary/secondary author ordering
    - Improved BISAC parsing with code lookup priority
    
    Args:
        xml_content: Raw XML bytes or string from BiblioShare
    
    Returns:
        Dict with parsed ONIX data, or {"_parse_error": "<reason>"} on failure
    """
    if not xml_content:
        return {"_parse_error": "Empty XML response"}
    
    try:
        if isinstance(xml_content, bytes):
            root = ET.fromstring(xml_content)
        else:
            root = ET.fromstring(xml_content.encode('utf-8'))
    except ET.ParseError as e:
        return {"_parse_error": f"Invalid XML: {e}"}
    
    # Check for error responses
    message_text = root.find(".//MessageText")
    if message_text is not None and message_text.text:
        error_msg = message_text.text.strip()
        return {"_parse_error": f"BiblioShare error: {error_msg}"}
    
    d = {}
    
    # Helper function for finding text
    def ft(*tags, parent=None):
        return _find_text(root, *tags, parent=parent)
    
    # ── Identifiers ───────────────────────────────────────────────────────
    for pid in root.iter('ProductIdentifier'):
        ptype = ft('ProductIDType', 'b221', parent=pid)
        val = ft('IDValue', 'b244', parent=pid)
        if ptype == '02':
            d['isbn_10'] = val
        elif ptype == '03':
            d['isbn_13'] = val
    
    # ── Contributors & Bio (WITH SEQUENCENUMBER SORTING) ──────────────────
    contributors_raw = []
    bio_raw = ""
    
    for contrib in root.iter('Contributor'):
        role = ft('ContributorRole', 'b035', parent=contrib)
        name = ft('PersonName', 'b036', 'PersonNameInverted', 'b037',
                  'CorporateName', 'b047', parent=contrib)
        country = ft('CountryCode', 'b251', parent=contrib)
        
        # Get SequenceNumber for proper ordering
        seq_num_str = ft('SequenceNumber', parent=contrib)
        try:
            seq_num = int(seq_num_str) if seq_num_str else 999
        except ValueError:
            seq_num = 999
        
        if name:
            contributors_raw.append({
                'name': name,
                'role': role,
                'country': country,
                'sequence': seq_num
            })
        
        # Extract bio with HTML cleaning - Use direct child find()
        bio_el = contrib.find('BiographicalNote') or contrib.find('b044')
        
        # Try alternative searches if needed
        if bio_el is None:
            bio_el = contrib.find('.//BiographicalNote') or contrib.find('.//b044')
        
        # Direct iteration approach - check each child manually
        if bio_el is None:
            for child in contrib:
                if child.tag == 'BiographicalNote':
                    bio_el = child
                    break
        
        if bio_el is not None and bio_el.text:
            raw_bio = bio_el.text.strip()
            if not bio_raw:  # Only use first bio found
                bio_raw = clean_html(raw_bio)
    
    # Sort by SequenceNumber to get correct primary/secondary author order
    contributors_raw.sort(key=lambda c: c['sequence'])
    
    d['contributors'] = contributors_raw
    d['bio'] = bio_raw
    d['cdn_creator'] = 'TRUE' if any(c.get('country') == 'CA' for c in contributors_raw) else 'FALSE'
    
    # ── Title / Subtitle ──────────────────────────────────────────────────
    d['title'] = ft('TitleText', 'b203', 'DistinctiveTitle')
    d['subtitle'] = ft('Subtitle', 'b029')
    
    # ── Series ────────────────────────────────────────────────────────────
    d['series_title'] = ft('TitleOfSeries', 'b018')
    d['series_number'] = ft('NumberWithinSeries', 'b019')
    d['volume_number'] = ft('VolumeNumber', 'b033')
    
    # ── Publisher / Publication Date ──────────────────────────────────────
    d['publisher'] = ft('PublisherName', 'b081')
    pub_raw = ft('PublicationDate', 'b003')
    d['publication_date'] = _parse_pub_date(pub_raw)
    
    # ── Product Form ──────────────────────────────────────────────────────
    pf = ft('ProductForm', 'b012')
    pfd = ft('ProductFormDetail', 'b333')
    form_name = FORM_MAP.get(pf, pf or "")
    form_detail = FORM_DETAIL_MAP.get(pfd, "")
    d['product_form'] = pf
    d['book_format'] = f"{form_name}, {form_detail}".strip(', ') if form_detail else form_name
    d['format_simple'] = form_name
    
    # ── Target Audience ───────────────────────────────────────────────────
    d['target_audience'] = AUDIENCE_MAP.get(ft('AudienceCode', 'b073'), 'General/Trade')
    
    # ── Descriptions (WITH HTML CLEANING) ─────────────────────────────────
    short_raw, long_raw, toc_raw = "", "", ""
    
    # ONIX 2.1 OtherText elements - Use direct child search like biblioNomics
    for ot in root.iter('OtherText'):
        code = ft('TextTypeCode', 'd102', parent=ot)
        
        # Check each possible text element individually
        text_candidates = ['Text', 'd104', 'TextContent', 'OtherTextContent']
        text_el = None
        for candidate in text_candidates:
            el = ot.find(candidate)
            if el is not None and el.text:
                text_el = el
                break
        
        if text_el is None and ot.text and ot.text.strip():
            raw_text = ot.text.strip()
            text = clean_html(raw_text)
        elif text_el is not None:
            raw_text = (text_el.text or "").strip()
            text = clean_html(raw_text)
        else:
            continue
        
        # Correct ONIX text type mapping
        if code == '01' and not long_raw:          # Code 01 = Long description
            long_raw = text
        elif code == '02' and not short_raw:       # Code 02 = Short description
            short_raw = text
        elif code == '03' and not long_raw:        # Code 03 = Long description fallback
            long_raw = text
        elif code == '04' and not toc_raw:         # Code 04 = Table of contents
            toc_raw = text
        elif code == '13' and not bio_raw:         # Code 13 = Author bio in OtherText
            bio_raw = text
    
    # ONIX 3.0 TextContent elements - Use direct child search
    for tc in root.iter('TextContent'):
        code = ft('TextType', 'x426', parent=tc)
        # Use direct child find() not descendant .//
        text_el = tc.find('Text') or tc.find('d104')
        if text_el is not None and text_el.text:
            raw_text = text_el.text.strip()
            text = clean_html(raw_text)
            # Correct ONIX 3.0 text type mapping
            if code == '01' and not long_raw:       # Code 01 = Long description
                long_raw = text
            elif code == '02' and not short_raw:    # Code 02 = Short description
                short_raw = text
            elif code == '03' and not long_raw:     # Code 03 = Long description fallback
                long_raw = text
            elif code == '08' and not toc_raw:      # Code 08 = Table of contents (ONIX 3.0)
                toc_raw = text
            elif code == '13' and not bio_raw:      # Code 13 = Author bio in TextContent
                bio_raw = text
    
    # If only a single long text came through under the 'short' slot, re-assign
    if short_raw and not long_raw and len(short_raw) > 400:
        long_raw, short_raw = short_raw, ""
    
    d['short_description'] = short_raw
    d['long_description'] = long_raw
    d['table_of_contents'] = toc_raw
    
    # ── Page Count ────────────────────────────────────────────────────────
    page_count = None
    
    # Try NumberOfPages first (like biblioNomics does)
    nop = root.find('.//NumberOfPages')
    if nop is not None and nop.text and nop.text.strip().isdigit():
        page_count = int(nop.text.strip())
    
    # Fallback to Extent elements
    if page_count is None:
        for ext in root.iter('Extent'):
            etype = ft('ExtentType', 'b218', parent=ext)
            eval_ = ft('ExtentValue', 'b219', parent=ext)
            if etype in ('00', '11') and eval_.isdigit():
                page_count = int(eval_)
                break
    
    d['page_count'] = page_count
    
    # ── Dimensions ────────────────────────────────────────────────────────
    d['dimensions'] = _parse_dimensions(root)
    
    # ── BISAC Subjects (WITH IMPROVED PARSING) ────────────────────────────
    subj_pairs = []
    
    # BASICMainSubject takes priority
    for ms in root.iter('BASICMainSubject'):
        if ms.text:
            c = ms.text.strip()
            subj_pairs.insert(0, (c, BISAC_CODE_TO_HEADING.get(c, '')))
    
    # Then other subjects
    for subj in root.iter('Subject'):
        scheme = ft('SubjectSchemeIdentifier', 'b067', 'x425', parent=subj)
        if scheme in ('10', '12'):
            c = ft('SubjectCode', 'b069', parent=subj)
            h = ft('SubjectHeadingText', 'b070', parent=subj)
            if c and not any(p[0] == c for p in subj_pairs):
                subj_pairs.append((c, h or BISAC_CODE_TO_HEADING.get(c, '')))
    
    d['bisac_pairs'] = subj_pairs
    
    # ── Awards ────────────────────────────────────────────────────────────
    awards = []
    for p in root.iter('Prize'):
        prize_name = ft('PrizeName', 'g126', parent=p)
        if prize_name:
            awards.append(prize_name)
    d['awards'] = "; ".join(awards)
    
    # ── Pricing ───────────────────────────────────────────────────────────
    prices = {}
    for price in root.iter('Price'):
        currency = ft('CurrencyCode', 'j152', parent=price)
        amount = ft('PriceAmount', 'j151', parent=price)
        try:
            prices[currency.upper()] = float(amount)
        except (ValueError, AttributeError, TypeError):
            pass
    d['prices'] = prices
    
    # ── Cover Image ───────────────────────────────────────────────────────
    cover_url = ""
    for mf in root.iter('MediaFile'):
        if ft('MediaFileTypeCode', 'f114', parent=mf) in ('04', '03'):
            cover_url = ft('MediaFileLink', 'f116', parent=mf)
            if cover_url:
                break
    
    if not cover_url:
        for sr in root.iter('SupportingResource'):
            if ft('ResourceContentType', parent=sr) == '01':
                rv = sr.find('.//ResourceVersion')
                if rv is not None:
                    cover_url = ft('ResourceLink', parent=rv)
                    if cover_url:
                        break
    
    d['cover_url'] = cover_url
    
    return d