# Project 6: Book Connection Data Enrichment

**Organization:** BIBLIOnomics  
**For:** Dalhousie University

---

## 1. Executive Summary

### 1.1 The Business

BIBLIOnomics is a B2B book gifting platform. We help businesses give meaningful book gifts by matching books to recipients based on personal connections—shared geography, industry, interests, and more.

### 1.2 The Problem

Standard book metadata tells you what a book is. It doesn't tell you who it connects to.

### 1.3 The Solution

Valuable information is already in the metadata—we just need to extract and map it.

Book metadata contains rich, unstructured data about authors, locations, industries, and themes. This project extracts and structures that hidden value into connection data that powers our matching engine.

### 1.4 Project Scope

Build an enrichment system that:
- Fetches book metadata from BiblioShare API (primary source) using ISBNs
- Supplements with Google Books and Open Library APIs (external sources)
- Extracts and maps connection data (geography, industry, author info)
- Outputs enriched data as a 75-column CSV file

**You deliver:** Source Code + Enriched CSV (500 books) + Connection Report

---

## 2. Input Specification

### 2.1 What You Receive

1. **ISBN List (CSV file)**—500 ISBNs to process, one per row
2. **BiblioShare API Token**—Authentication for BiblioShare API
3. **This Specification**—Defines 75 output fields and expected format

### 2.2 BiblioShare API (Primary Source)

**Endpoint:**
```
GET https://biblioshare.ca/BNCServices/BNCServices.asmx/ONIX
```

**Parameters:**
- `Token`: API authentication token (provided separately)
- `EAN`: ISBN-13 of the book to look up

**Example Request:**
```
https://biblioshare.ca/BNCServices/BNCServices.asmx/ONIX?Token=[TOKEN]&EAN=9780785291909
```

### 2.3 Example API Response

The BiblioShare API returns ONIX-formatted data. Below is a real example response (JSON format):

```json
{
  "data": {
    "Product": {
      "RecordReference": [9780785291909],
      "ProductIdentifier": [
        {"ProductIDType": ["02"], "IDValue": ["0785291903"]},
        {"ProductIDType": ["03"], "IDValue": [9780785291909]}
      ],
      "ProductForm": ["BB"],
      "ProductFormDescription": ["Hardcover, Jacketed"],
      "Title": [{
        "TitleType": ["01"],
        "TitleText": ["Power Moves"],
        "Subtitle": ["Ignite Your Confidence and Become a Force"]
      }],
      "Contributor": [{
        "SequenceNumber": [1],
        "ContributorRole": ["A01"],
        "PersonName": ["Sarah Jakes Roberts"],
        "BiographicalNote": ["<p>Sarah Jakes Roberts is a <em>New York Times</em> bestselling author, speaker, entrepreneur, and philanthropist. She is the founder of Woman Evolve... Alongside her husband, Toure Roberts, she serves as an Assistant Pastor at The Potter's House Dallas...</p>"]
      }],
      "Language": [{"LanguageRole": ["01"], "LanguageCode": ["eng"]}],
      "NumberOfPages": [224],
      "BASICMainSubject": ["REL012130"],
      "Subject": [
        {"SubjectSchemeIdentifier": [10], "SubjectCode": ["REL050000"], "SubjectHeadingText": ["RELIGION / Christian Ministry / Counseling & Recovery"]},
        {"SubjectSchemeIdentifier": [10], "SubjectCode": ["SEL031000"], "SubjectHeadingText": ["SELF-HELP / Personal Growth / General"]}
      ],
      "OtherText": [
        {"TextTypeCode": ["01"], "Text": ["<p><strong>Unleash the superpower of being yourself...</strong></p>"]},
        {"TextTypeCode": ["02"], "Text": ["New full-length trade book from the bestselling author of Woman Evolve."]}
      ],
      "MediaFile": [{
        "MediaFileTypeCode": ["04"],
        "MediaFileLink": ["http://media.zondervan.com/.../9780785291909.jpg"]
      }],
      "Publisher": [{"PublisherName": ["Thomas Nelson"]}],
      "CityOfPublication": ["Nashville"],
      "CountryOfPublication": ["US"],
      "PublicationDate": [20240430],
      "Measure": [
        {"MeasureTypeCode": ["01"], "Measurement": [9.3], "MeasureUnitCode": ["in"]},
        {"MeasureTypeCode": ["02"], "Measurement": [6.3], "MeasureUnitCode": ["in"]},
        {"MeasureTypeCode": ["03"], "Measurement": ["0.90"], "MeasureUnitCode": ["in"]},
        {"MeasureTypeCode": ["08"], "Measurement": ["0.770"], "MeasureUnitCode": ["lb"]}
      ],
      "SupplyDetail": [{
        "Price": [
          {"PriceAmount": [36.99], "CurrencyCode": ["CAD"]},
          {"PriceAmount": [29.99], "CurrencyCode": ["USD"]}
        ]
      }]
    }
  }
}
```

### 2.4 External Sources (Supplementary)

**Google Books API**
- Endpoint: `GET https://www.googleapis.com/books/v1/volumes?q=isbn:{ISBN}`
- No authentication required
- Use for: `averageRating`, `ratingsCount`

**Open Library API**
- Endpoint: `GET https://openlibrary.org/isbn/{ISBN}.json`
- No authentication required
- Use for: Availability check

**Data Source Priority:**
1. **BiblioShare (Primary)**—Canadian metadata, pricing, physical specs
2. **Google Books (Secondary)**—Ratings
3. **Open Library (Tertiary)**—Availability check

---

## 3. Complete Flow Example

This example shows the complete extraction and mapping flow for one book.

### 3.1 Step 1: Fetch Raw Data

**Input ISBN:** `9780785291909`

Call BiblioShare API → Receive ONIX data (as shown in Section 2.3)

### 3.2 Step 2: Extract Source Fields (Section A)

From the ONIX response, extract and map:

```
title:              "Power Moves"
subtitle:           "Ignite Your Confidence and Become a Force"
primary_author:     "Sarah Jakes Roberts"
isbn_13:            "9780785291909"
isbn_10:            "0785291903"
book_format:        "Hardcover, Jacketed"
publisher:          "Thomas Nelson"
publication_date:   "2024-04-30"
page_count:         224
list_price_cad:     36.99
list_price_usd:     29.99

author_description (after HTML stripping):
"Sarah Jakes Roberts is a New York Times bestselling author, speaker, entrepreneur, and philanthropist. She is the founder of Woman Evolve... Alongside her husband, Toure Roberts, she serves as an Assistant Pastor at The Potter's House Dallas..."

bisac_primary_code: "REL012130"
bisac_level_1:      "RELIGION"
bisac_level_2:      "Christian Ministry"
bisac_level_3:      "Counseling & Recovery"
```

### 3.3 Step 3: Extract Physical Dimensions (Section B)

From ONIX Measure array:

```
book_height_in:     9.3
book_width_in:      6.3
spine_thickness_in: 0.90
book_weight_lb:     0.770
cover_dimensions:   "9.3 x 6.3"
book_size_category: "Standard" (Height 7-10" AND Width 5-7")
```

### 3.4 Step 4: Extract Author Bio Data (Section C)

Parse author description using pattern matching:

**Input text:**
```
"Sarah Jakes Roberts is a New York Times bestselling author, speaker, entrepreneur, and philanthropist... serves as an Assistant Pastor at The Potter's House Dallas..."
```

**Extraction results:**
```
author_location_raw:    "Dallas" (from "The Potter's House Dallas")
author_province:        "USA" (Dallas is not Canadian)
author_region:          "USA"
author_profession_raw:  "bestselling author, speaker, entrepreneur, and philanthropist"
author_institution:     "The Potter's House Dallas"
author_bio_richness:    "Rich" (word count > 100)
author_summary:         "Sarah Jakes Roberts is a USA-based author, speaker, entrepreneur, and philanthropist at The Potter's House Dallas"
```

### 3.5 Step 5: Derive Connection Fields (Section D)

Apply deterministic rules:

```
primary_industry:       "General Interest" (RELIGION -> General Interest)
gift_price_tier:        "Premium" ($36.99 CAD in $35-50 range)
book_length_category:   "Standard" (224 pages in 150-300 range)
publisher_region:       "USA" (Thomas Nelson -> USA)
book_themes_bisac:      "RELIGION / Christian Ministry / Counseling"
locations_mentioned:    "Dallas" (from description)
time_period_mentioned:  "" (no year/decade found)
corporate_appropriate:  TRUE (no flagged BISAC codes)
```

### 3.6 Step 6: Fetch External Data (Section E)

**Google Books API call → Found**
```
google_books_rating:        4.5
google_books_rating_count:  1247
google_books_available:     TRUE
```

**Open Library API call → Found**
```
open_library_available:     TRUE
```

**Constructed URLs:**
```
amazon_ca_url:  "https://amazon.ca/dp/0785291903"
goodreads_url:  "https://goodreads.com/book/isbn/9780785291909"
```

### 3.7 Step 7: Generate Metadata (Section F)

```
enrichment_status:    "Complete"
enrichment_date:      "2026-01-21"
confidence_score:     85 (rich bio + external data available)
data_richness:        "Rich"
data_sources:         "BiblioShare | Google Books | Open Library"
fields_populated:     68
verification_status:  "Verified"
last_updated:         "2026-01-21"
```

### 3.8 Step 8: Capture Extras (Section G)

```
extracted_extras: "[UNVERIFIED] Other works: Woman Evolve
                   [UNVERIFIED] Role: founder of Woman Evolve
                   [UNVERIFIED] Spouse: Toure Roberts"
```

---

## 4. Field Definitions (75 Fields)

### 4.1 Section A: Source Data (Fields 1–35)

Passthrough from BiblioShare with minimal transformation.

| # | Field | Description |
|---|-------|-------------|
| 1 | `id` | Generate unique ID (UUID or sequential) |
| 2 | `title` | Book title |
| 3 | `primary_author` | Main author name |
| 4 | `isbn_13` | 13-digit ISBN |
| 5 | `book_format` | Physical format (e.g., "Hardcover, Jacketed") |
| 6 | `cdn_creator` | Boolean: TRUE if Canadian creator (from ONIX) |
| 7 | `short_description` | Marketing blurb (OtherText type 02) |
| 8 | `genre_tags` | Genre classification (from BISAC level 1) |
| 9 | `cover_source` | Cover image URL |
| 10 | `isbn_10` | 10-digit ISBN |
| 11 | `subtitle` | Book subtitle |
| 12 | `series_title` | Series name if applicable |
| 13 | `publisher` | Publisher name |
| 14 | `author_description` | Raw author bio (strip HTML tags) |
| 15 | `awards` | Awards won |
| 16 | `bisac_primary_code` | Primary BISAC code (e.g., "REL012130") |
| 17 | `bisac_secondary_code` | Secondary BISAC code |
| 18 | `bisac_tertiary_code` | Tertiary BISAC code |
| 19 | `bisac_level_1` | BISAC top category (e.g., "RELIGION") |
| 20 | `bisac_level_2` | BISAC second level |
| 21 | `bisac_level_3` | BISAC third level |
| 22 | `bisac_level_4` | BISAC fourth level |
| 23 | `series_number` | Position in series |
| 24 | `volume_number` | Volume number |
| 25 | `table_of_contents` | TOC if available |
| 26 | `all_authors` | Comma-separated list of all authors |
| 27 | `secondary_author` | Second contributor |
| 28 | `publication_date` | Format: YYYY-MM-DD |
| 29 | `format` | Hardcover, Paperback, etc. |
| 30 | `long_description` | Full marketing description (strip HTML) |
| 31 | `page_count` | Number of pages |
| 32 | `target_audience` | Intended audience |
| 33 | `list_price_cad` | Canadian retail price |
| 34 | `list_price_usd` | US retail price |
| 35 | `reading_level` | Reading level if specified |

**BISAC Code Parsing:** Use `SubjectHeadingText` field (e.g., "RELIGION / Christian Ministry / Counseling") and split by " / ".

**Resource:** https://www.bisg.org/complete-bisac-subject-headings-list

**HTML Stripping:** ONIX text fields contain HTML tags. Strip all HTML before storing.

### 4.2 Section B: Physical Dimensions (Fields 36–45)

Extracted from ONIX Measure data.

| # | Field | Description |
|---|-------|-------------|
| 36 | `book_height_in` | Height in inches |
| 37 | `book_height_mm` | Height in millimeters |
| 38 | `book_width_in` | Width in inches |
| 39 | `book_width_mm` | Width in millimeters |
| 40 | `spine_thickness_in` | Spine in inches |
| 41 | `spine_thickness_mm` | Spine in millimeters |
| 42 | `book_weight_lb` | Weight in pounds |
| 43 | `book_weight_g` | Weight in grams |
| 44 | `cover_dimensions` | Format: "H x W in" (e.g., "9.5 x 6.3") |
| 45 | `book_size_category` | Pocket / Standard / Large / Coffee Table / Unknown |

**ONIX Measure Type Codes:** 01=Height, 02=Width, 03=Spine, 08=Weight

**Book Size Category Logic:**
- **Pocket:** Height < 7" OR Width < 5"
- **Standard:** Height 7–10" AND Width 5–7"
- **Large:** Height 10–12" OR Width 7–9"
- **Coffee Table:** Height > 12" OR Width > 9"
- **Unknown:** No dimension data available

### 4.3 Section C: Author Bio Extraction (Fields 46–52)

Extracted from author description field using pattern matching.

| # | Field | Description |
|---|-------|-------------|
| 46 | `author_location_raw` | Location phrase verbatim (e.g., "from Halifax, NS") |
| 47 | `author_province` | Province mapped from city (e.g., "Nova Scotia") |
| 48 | `author_region` | Region derived from province (e.g., "Atlantic") |
| 49 | `author_profession_raw` | Profession verbatim (e.g., "food writer") |
| 50 | `author_institution` | Institution/employer if mentioned |
| 51 | `author_bio_richness` | Rich (>100 words) / Moderate (50–100) / Sparse (<50) / None |
| 52 | `author_summary` | Human-readable combined summary of author (see below) |

**Province Values:** Nova Scotia, New Brunswick, Prince Edward Island, Newfoundland and Labrador, Quebec, Ontario, Manitoba, Saskatchewan, Alberta, British Columbia, Yukon, Northwest Territories, Nunavut, USA, International, Unknown

**Region Mapping:**
- **Atlantic:** NS, NB, PE, NL
- **Quebec:** QC
- **Ontario:** ON
- **Prairies:** MB, SK, AB
- **British Columbia:** BC
- **North:** YT, NT, NU

**Author Summary Field:**

Combine verified extraction data into a human-readable sentence:

```
Template: "[Name] is a [region]-based [profession] at [institution]"

Examples:
- "Elisabeth Bailey is an Atlantic-based food and gardening writer"
- "Dan Martell is a Canadian entrepreneur"
- "Sarah Jakes Roberts is a USA-based author, speaker, and philanthropist at The Potter's House Dallas"

Rules:
- Only include verified data from fields 46-51
- If location unknown, omit region
- If no institution, omit "at [institution]"
- If no profession, use "author"
```

**Extraction Principle:** If uncertain, leave blank. Never guess.

### 4.4 Section D: Connection Fields (Fields 53–60)

Deterministic rules and verifiable extraction.

| # | Field | Description |
|---|-------|-------------|
| 53 | `primary_industry` | Mapped from BISAC (see Appendix A) |
| 54 | `gift_price_tier` | Budget (<$20) / Standard ($20–35) / Premium ($35–50) / Luxury ($50+) |
| 55 | `book_length_category` | Quick Read (<150) / Standard (150–300) / Substantial (300–450) / Epic (450+) |
| 56 | `publisher_region` | Publisher mapped to region (see Appendix B) |
| 57 | `book_themes_bisac` | BISAC hierarchy concatenated |
| 58 | `locations_mentioned` | Places found in description, pipe-delimited |
| 59 | `time_period_mentioned` | Years/decades found in description |
| 60 | `corporate_appropriate` | Boolean: FALSE if BISAC contains flagged categories |

### 4.5 Section E: External Sources (Fields 61–66)

From Google Books and Open Library APIs.

| # | Field | Description |
|---|-------|-------------|
| 61 | `google_books_rating` | Average rating from Google Books |
| 62 | `google_books_rating_count` | Number of ratings |
| 63 | `google_books_available` | Boolean: TRUE if found |
| 64 | `open_library_available` | Boolean: TRUE if found |
| 65 | `amazon_ca_url` | Constructed: `https://amazon.ca/dp/{ISBN-10}` |
| 66 | `goodreads_url` | Constructed: `https://goodreads.com/book/isbn/{ISBN-13}` |

### 4.6 Section F: Enrichment Metadata (Fields 67–74)

System-generated fields.

| # | Field | Description |
|---|-------|-------------|
| 67 | `enrichment_status` | Complete / Partial / Failed / Pending |
| 68 | `enrichment_date` | YYYY-MM-DD |
| 69 | `confidence_score` | 0–100 calculated score |
| 70 | `data_richness` | Rich / Moderate / Sparse / Minimal |
| 71 | `data_sources` | Pipe-delimited: BiblioShare|Google Books|Open Library |
| 72 | `fields_populated` | Count of non-empty fields (0–75) |
| 73 | `verification_status` | Verified / Partial / Unverified |
| 74 | `last_updated` | YYYY-MM-DD |

### 4.7 Section G: Extracted Extras (Field 75)

Catch-all for unverified data.

| # | Field | Description |
|---|-------|-------------|
| 75 | `extracted_extras` | Unstructured data with [UNVERIFIED] labels |

---

## 5. Deliverables

### 5.1 Primary Deliverables

1. **Source Code**
   - Complete, runnable enrichment system
   - README with setup instructions
   - Runnable with single command (e.g., `python enrich.py input.csv output.csv`)
   - Include lookup tables you created (BISAC mapping, publisher regions, etc.)

2. **Enriched CSV**
   - 500 books processed
   - One row per ISBN, 75 columns as specified
   - UTF-8 encoding

3. **Connection & Relationship Report**
   - Demonstrate that your system extracts meaningful connection data
   - Show geographic, industry, and Canadian content connections
   - Include data quality metrics

### 5.2 Supporting Deliverables

4. Architecture Documentation (1–2 pages)
5. Setup & Run Guide
6. Live Demo

---

## Appendix A: BISAC to Industry Mapping (Sample)

| BISAC Category | Industry |
|----------------|----------|
| BUSINESS & ECONOMICS | Finance & Banking |
| COMPUTERS | Technology |
| COOKING | Agriculture & Food |
| EDUCATION | Education |
| HEALTH & FITNESS | Healthcare & Pharma |
| LAW | Legal |
| MEDICAL | Healthcare & Pharma |
| POLITICAL SCIENCE | Government & Public Sector |
| TECHNOLOGY & ENGINEERING | Technology |
| TRAVEL | Tourism & Hospitality |
| GARDENING | Agriculture & Food |
| ARCHITECTURE | Real Estate |
| HOUSE & HOME | Real Estate |
| CRAFTS & HOBBIES | Retail & Consumer |
| PETS | Retail & Consumer |
| TRANSPORTATION | Manufacturing |
| JUVENILE | Education |
| All others | General Interest |

---

## Appendix B: Publisher to Region Mapping (Sample)

**Atlantic Publishers:**
- Nimbus Publishing
- Pottersfield Press
- Goose Lane Editions
- Breakwater Books
- Flanker Press
- Acorn Press
- Cape Breton University Press
- Formac Publishing