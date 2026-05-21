"""
BIBLIOnomics — Configuration & Mapping Tables
All constants, API endpoints, and mapping tables from the specification appendices.
"""

# ── API Configuration ────────────────────────────────────────────────────────

BIBLIOSHARE_ENDPOINT = (
    "https://biblioshare.ca/BNCServices/BNCServices.asmx/ONIX"
)
GOOGLE_BOOKS_ENDPOINT = (
    "https://www.googleapis.com/books/v1/volumes"
)
OPEN_LIBRARY_ENDPOINT = "https://openlibrary.org/isbn/{isbn}.json"

# Rate limits (seconds between calls)
RATE_LIMIT_BIBLIOSHARE = 0.5
RATE_LIMIT_GOOGLE = 0.2
RATE_LIMIT_OPENLIBRARY = 0.2

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 1.5  # 1.5s, 2.25s, 3.375s

# Cache TTL (seconds) — 7 days
CACHE_TTL_SECONDS = 7 * 24 * 3600


# ── Appendix A: BISAC to Industry Mapping ────────────────────────────────────

BISAC_TO_INDUSTRY = {
    "BUSINESS & ECONOMICS":      "Finance & Banking",
    "COMPUTERS":                  "Technology",
    "COOKING":                    "Agriculture & Food",
    "EDUCATION":                  "Education",
    "HEALTH & FITNESS":           "Healthcare & Pharma",
    "LAW":                        "Legal",
    "MEDICAL":                    "Healthcare & Pharma",
    "POLITICAL SCIENCE":          "Government & Public Sector",
    "TECHNOLOGY & ENGINEERING":   "Technology",
    "TRAVEL":                     "Tourism & Hospitality",
    "GARDENING":                  "Agriculture & Food",
    "ARCHITECTURE":               "Real Estate",
    "HOUSE & HOME":               "Real Estate",
    "CRAFTS & HOBBIES":           "Retail & Consumer",
    "PETS":                       "Retail & Consumer",
    "TRANSPORTATION":             "Manufacturing",
    "JUVENILE FICTION":           "Education",
    "JUVENILE NONFICTION":        "Education",
    "YOUNG ADULT FICTION":        "Education",
    "YOUNG ADULT NONFICTION":     "Education",
}
# Default for any BISAC level-1 not in mapping
BISAC_INDUSTRY_DEFAULT = "General Interest"


# ── Appendix B: Publisher to Region Mapping ──────────────────────────────────

PUBLISHER_REGION_PATTERNS = [
    # Atlantic
    (["Nimbus", "Pottersfield", "Goose Lane", "Breakwater",
      "Flanker", "Acorn Press", "Cape Breton University Press",
      "Formac"], "Atlantic"),
    # Quebec
    (["Véhicule", "Vehicule", "McGill-Queen", "Linda Leith",
      "Baraka"], "Quebec"),
    # Ontario
    (["House of Anansi", "Anansi", "ECW Press", "Dundurn",
      "Coach House", "University of Toronto Press",
      "Cormorant", "Second Story Press",
      "Random House Canada", "Penguin Canada",
      "HarperCollins Canada"], "Ontario"),
    # Prairies
    (["Thistledown", "NeWest Press", "Great Plains",
      "University of Alberta Press", "University of Manitoba Press",
      "Freehand Books"], "Prairies"),
    # British Columbia
    (["Talonbooks", "Douglas & McIntyre", "Douglas and McIntyre",
      "Harbour Publishing", "Greystone", "Arsenal Pulp",
      "New Star Books", "Orca Book"], "British Columbia"),
    # USA
    (["Thomas Nelson", "Penguin Publishing Group", "HarperCollins",
      "Simon & Schuster", "Simon and Schuster", "Random House",
      "Hachette", "Macmillan", "Wiley", "Scholastic",
      "Little, Brown", "Knopf", "Crown", "Doubleday",
      "Zondervan", "Houghton Mifflin"], "USA"),
]


# ── Appendix C: Province to Region Mapping ───────────────────────────────────

PROVINCE_ABBREV_TO_FULL = {
    "NS": "Nova Scotia",
    "NB": "New Brunswick",
    "PE": "Prince Edward Island",
    "NL": "Newfoundland and Labrador",
    "QC": "Quebec",
    "ON": "Ontario",
    "MB": "Manitoba",
    "SK": "Saskatchewan",
    "AB": "Alberta",
    "BC": "British Columbia",
    "YT": "Yukon",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
}

PROVINCE_TO_REGION = {
    "Nova Scotia":                "Atlantic",
    "New Brunswick":              "Atlantic",
    "Prince Edward Island":       "Atlantic",
    "Newfoundland and Labrador":  "Atlantic",
    "Quebec":                     "Quebec",
    "Ontario":                    "Ontario",
    "Manitoba":                   "Prairies",
    "Saskatchewan":               "Prairies",
    "Alberta":                    "Prairies",
    "British Columbia":           "British Columbia",
    "Yukon":                      "North",
    "Northwest Territories":      "North",
    "Nunavut":                    "North",
    "USA":                        "USA",
    "International":              "International",
}


# ── Canadian City to Province Lookup ─────────────────────────────────────────

CITY_TO_PROVINCE = {
    # Atlantic
    "Halifax":       "Nova Scotia",
    "Dartmouth":     "Nova Scotia",
    "Sydney":        "Nova Scotia",
    "Fredericton":   "New Brunswick",
    "Saint John":    "New Brunswick",
    "Moncton":       "New Brunswick",
    "Charlottetown": "Prince Edward Island",
    "St. John's":    "Newfoundland and Labrador",
    "Corner Brook":  "Newfoundland and Labrador",
    # Quebec
    "Montreal":      "Quebec",
    "Montréal":      "Quebec",
    "Quebec City":   "Quebec",
    "Québec":        "Quebec",
    "Gatineau":      "Quebec",
    "Sherbrooke":    "Quebec",
    "Laval":         "Quebec",
    # Ontario
    "Toronto":       "Ontario",
    "Ottawa":        "Ontario",
    "Hamilton":      "Ontario",
    "London":        "Ontario",
    "Kitchener":     "Ontario",
    "Windsor":       "Ontario",
    "Kingston":      "Ontario",
    "Guelph":        "Ontario",
    "Thunder Bay":   "Ontario",
    "Sudbury":       "Ontario",
    "Waterloo":      "Ontario",
    "Peterborough":  "Ontario",
    # Prairies
    "Winnipeg":      "Manitoba",
    "Brandon":       "Manitoba",
    "Saskatoon":     "Saskatchewan",
    "Regina":        "Saskatchewan",
    "Calgary":       "Alberta",
    "Edmonton":      "Alberta",
    "Lethbridge":    "Alberta",
    "Red Deer":      "Alberta",
    # British Columbia
    "Vancouver":     "British Columbia",
    "Victoria":      "British Columbia",
    "Kelowna":       "British Columbia",
    "Nanaimo":       "British Columbia",
    "Kamloops":      "British Columbia",
    "Prince George": "British Columbia",
    # North
    "Whitehorse":    "Yukon",
    "Yellowknife":   "Northwest Territories",
    "Iqaluit":       "Nunavut",
}

# Reverse lookup: province abbreviation from full name
PROVINCE_FULL_TO_ABBREV = {v: k for k, v in PROVINCE_ABBREV_TO_FULL.items()}


# ── BISAC Code to Heading Lookup ─────────────────────────────────────────────
# A subset of common BISAC codes → heading text for fallback when
# SubjectHeadingText is absent. Codes map to "LEVEL1 / LEVEL2 / LEVEL3".

BISAC_CODE_TO_HEADING = {
    # Business & Economics
    "BUS000000": "BUSINESS & ECONOMICS / General",
    "BUS001000": "BUSINESS & ECONOMICS / Accounting / General",
    "BUS012000": "BUSINESS & ECONOMICS / Careers / General",
    "BUS017000": "BUSINESS & ECONOMICS / Decision-Making & Problem Solving",
    "BUS020000": "BUSINESS & ECONOMICS / Development / Economic Development",
    "BUS025000": "BUSINESS & ECONOMICS / Entrepreneurship",
    "BUS036000": "BUSINESS & ECONOMICS / Investments & Securities / General",
    "BUS041000": "BUSINESS & ECONOMICS / Management",
    "BUS042000": "BUSINESS & ECONOMICS / Management Science",
    "BUS046000": "BUSINESS & ECONOMICS / Mentoring & Coaching",
    "BUS050000": "BUSINESS & ECONOMICS / Personal Finance / General",
    "BUS070000": "BUSINESS & ECONOMICS / Personal Success",
    "BUS071000": "BUSINESS & ECONOMICS / Leadership",
    # Computers
    "COM000000": "COMPUTERS / General",
    "COM051000": "COMPUTERS / Programming / General",
    "COM060000": "COMPUTERS / Internet / General",
    "COM018000": "COMPUTERS / Data Science / General",
    # Cooking
    "CKB000000": "COOKING / General",
    "CKB014000": "COOKING / Regional & Ethnic / Canadian",
    # Education
    "EDU000000": "EDUCATION / General",
    "EDU016000": "EDUCATION / Higher",
    # Fiction
    "FIC000000": "FICTION / General",
    "FIC005000": "FICTION / Erotica / General",
    "FIC014000": "FICTION / Historical / General",
    "FIC019000": "FICTION / Literary",
    "FIC027000": "FICTION / Romance / General",
    "FIC028000": "FICTION / Science Fiction / General",
    "FIC031000": "FICTION / Thrillers / General",
    # Health & Fitness
    "HEA000000": "HEALTH & FITNESS / General",
    "HEA010000": "HEALTH & FITNESS / Healthy Living",
    # History
    "HIS000000": "HISTORY / General",
    "HIS006000": "HISTORY / Canada / General",
    "HIS051000": "HISTORY / Exploration & Discovery",
    "HIS052000": "HISTORY / Historical Geography",
    # Humor
    "HUM000000": "HUMOR / General",
    "HUM006000": "HUMOR / Topic / Political",
    # Juvenile
    "JUV000000": "JUVENILE FICTION / General",
    "JNF000000": "JUVENILE NONFICTION / General",
    # Law
    "LAW000000": "LAW / General",
    # Medical
    "MED000000": "MEDICAL / General",
    # Political Science
    "POL000000": "POLITICAL SCIENCE / General",
    "POL028000": "POLITICAL SCIENCE / Political Ideologies / Anarchism & Libertarianism",
    "POL042000": "POLITICAL SCIENCE / Political Ideologies / Communism, Post-Communism & Socialism",
    "POL044000": "POLITICAL SCIENCE / Political Ideologies / Fascism & Totalitarianism",
    # Religion
    "REL000000": "RELIGION / General",
    "REL012000": "RELIGION / Christian Living / General",
    "REL012040": "RELIGION / Christian Living / Inspirational",
    "REL012070": "RELIGION / Christian Living / Personal Growth",
    "REL012130": "RELIGION / Christian Living / Women's Interests",
    "REL012140": "RELIGION / Christian Living / Calling & Vocation",
    "REL050000": "RELIGION / Christian Ministry / Counseling & Recovery",
    "REL108030": "RELIGION / Christian Living / Leadership & Mentoring",
    "REL118000": "RELIGION / Occultism",
    # Body, Mind & Spirit
    "OCC000000": "BODY, MIND & SPIRIT / General",
    "OCC026000": "BODY, MIND & SPIRIT / Witchcraft",
    # Self-Help
    "SEL000000": "SELF-HELP / General",
    "SEL021000": "SELF-HELP / Motivational & Inspirational",
    "SEL027000": "SELF-HELP / Personal Growth / Success",
    "SEL031000": "SELF-HELP / Personal Growth / General",
    "SEL034000": "SELF-HELP / Sexual Instruction",
    # Technology & Engineering
    "TEC000000": "TECHNOLOGY & ENGINEERING / General",
    # Transportation
    "TRA000000": "TRANSPORTATION / General",
    # Travel
    "TRV000000": "TRAVEL / General",
    "TRV006000": "TRAVEL / Canada / General",
    # True Crime
    "TRU000000": "TRUE CRIME / General",
    "TRU002000": "TRUE CRIME / Murder / General",
    # Gardening
    "GAR000000": "GARDENING / General",
    # Architecture
    "ARC000000": "ARCHITECTURE / General",
    # House & Home
    "HOM000000": "HOUSE & HOME / General",
    # Crafts & Hobbies
    "CRA000000": "CRAFTS & HOBBIES / General",
    # Pets
    "PET000000": "PETS / General",
}


# ── Flagged BISAC Codes (corporate_appropriate = FALSE) ──────────────────────

FLAGGED_BISAC_PREFIXES = [
    "FIC005",   # FICTION / Erotica
    "FIC027",   # FICTION / Romance / Erotica (sub-codes)
    "OCC026",   # BODY, MIND & SPIRIT / Witchcraft
    "HUM006",   # HUMOR / Topic / Political
    "POL042",   # POLITICAL SCIENCE / Political Ideologies / Communism
    "POL044",   # POLITICAL SCIENCE / Political Ideologies / Fascism
    "POL028",   # POLITICAL SCIENCE / Political Ideologies / Anarchism
    "REL118",   # RELIGION / Occultism
    "TRU002",   # TRUE CRIME / Murder
    "SEL034",   # SELF-HELP / Sexual Instruction
]


# ── Location Signal Verbs (for author location disambiguation) ───────────────

LOCATION_SIGNAL_VERBS = {
    "lives", "based", "resides", "from", "native", "born", "grew",
    "raised", "settled", "moved", "relocated",
}


# ── Region Display Labels (for author summary) ──────────────────────────────

REGION_DISPLAY_LABELS = {
    "USA":           "US",
    "International": None,  # suppress region in summary
}


# ── Profession Modifier Words (to strip from raw professions) ────────────────

PROFESSION_MODIFIERS = {
    "bestselling", "best-selling", "award-winning", "acclaimed",
    "celebrated", "renowned", "prominent", "noted", "distinguished",
    "internationally", "nationally", "new", "york", "times",
    "critically", "widely", "highly", "well-known", "prolific",
    "emerging", "established", "leading", "top",
}


# ── Award Extraction Patterns ───────────────────────────────────────────────

AWARD_PATTERNS = [
    r"[Ww]inner of (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Rr]ecipient of (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Ll]ong-?listed for (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Ss]hort-?listed for (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Nn]ominated for (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Aa]warded (?:the )?(.+?)(?:\.|,|;|\n|$)",
    r"[Ff]inalist for (?:the )?(.+?)(?:\.|,|;|\n|$)",
]


# ── 75-Column CSV Field Names (in spec order) ───────────────────────────────

CSV_FIELD_NAMES = [
    # Section A: Source Data (1-35)
    "id",
    "title",
    "primary_author",
    "isbn_13",
    "book_format",
    "cdn_creator",
    "short_description",
    "genre_tags",
    "cover_source",
    "isbn_10",
    "subtitle",
    "series_title",
    "publisher",
    "author_description",
    "awards",
    "bisac_primary_code",
    "bisac_secondary_code",
    "bisac_tertiary_code",
    "bisac_level_1",
    "bisac_level_2",
    "bisac_level_3",
    "bisac_level_4",
    "series_number",
    "volume_number",
    "table_of_contents",
    "all_authors",
    "secondary_author",
    "publication_date",
    "format",
    "long_description",
    "page_count",
    "target_audience",
    "list_price_cad",
    "list_price_usd",
    "reading_level",
    # Section B: Physical Dimensions (36-45)
    "book_height_in",
    "book_height_mm",
    "book_width_in",
    "book_width_mm",
    "spine_thickness_in",
    "spine_thickness_mm",
    "book_weight_lb",
    "book_weight_g",
    "cover_dimensions",
    "book_size_category",
    # Section C: Author Bio Extraction (46-52)
    "author_location_raw",
    "author_province",
    "author_region",
    "author_profession_raw",
    "author_institution",
    "author_bio_richness",
    "author_summary",
    # Section D: Connection Fields (53-60)
    "primary_industry",
    "gift_price_tier",
    "book_length_category",
    "publisher_region",
    "book_themes_bisac",
    "locations_mentioned",
    "time_period_mentioned",
    "corporate_appropriate",
    # Section E: External Sources (61-66)
    "google_books_rating",
    "google_books_rating_count",
    "google_books_available",
    "open_library_available",
    "amazon_ca_url",
    "goodreads_url",
    # Section F: Enrichment Metadata (67-74)
    "enrichment_status",
    "enrichment_date",
    "confidence_score",
    "data_richness",
    "data_sources",
    "fields_populated",
    "verification_status",
    "last_updated",
    # Section G: Extracted Extras (75)
    "extracted_extras",
]

assert len(CSV_FIELD_NAMES) == 75, (
    f"Expected 75 fields, got {len(CSV_FIELD_NAMES)}"
)