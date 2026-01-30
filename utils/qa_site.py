#!/usr/bin/env python3
"""
QA Site Integrity Checker
-------------------------
Verifies that the static site in docs/ has all required files, 
that data files referenced in index.html exist/are valid,
and performs logical checks on the content (titles, duplicates).
"""

import sys
import json
import logging
import re
from pathlib import Path
from bs4 import BeautifulSoup
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DOCS_DIR = Path("docs")
DATA_DIR = DOCS_DIR / "data"

REQUIRED_FILES = [
    "index.html",
    "app.js",
    "styles.css"
]

def check_core_files():
    """Checks for existence of core static files."""
    missing = []
    for fname in REQUIRED_FILES:
        fpath = DOCS_DIR / fname
        if not fpath.exists():
            missing.append(fname)
    
    if missing:
        logger.error(f"Missing core files in {DOCS_DIR}: {', '.join(missing)}")
        return False
    logger.info("Core static files present.")
    return True

def get_referenced_laws_with_titles():
    """Extracts law IDs and their display titles from index.html."""
    index_path = DOCS_DIR / "index.html"
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        
        select = soup.find("select", id="law-select")
        if not select:
            logger.error("Could not find <select id='law-select'> in index.html")
            return {}
        
        options = select.find_all("option")
        # Return dict {id: title}
        laws = {opt["value"]: opt.text.strip() for opt in options if opt.has_attr("value")}
        logger.info(f"Found {len(laws)} law references in index.html")
        return laws
    except Exception as e:
        logger.error(f"Failed to parse index.html: {e}")
        return {}

def normalize_string(s):
    """Simple normalization for fuzzy comparison."""
    if not s: return ""
    return re.sub(r'\s+', ' ', s.lower().replace('.', '').replace(',', '').strip())

def check_title_consistency(law_id, html_title, json_data):
    """
    Checks if the title in HTML roughly matches the title in JSON.
    Returns list of issues (strings).
    """
    issues = []
    json_title = json_data.get("ley", {}).get("nombre", "")
    
    # Common words to ignore in this domain
    stopwords = {
        "de", "del", "la", "las", "el", "los", "y", "o", "para", "en", 
        "ley", "estatuto", "regimen", "nacional", "convenciones", "colectivas", "trabajo"
    }
    
    # Clean HTML title: Remove "Ley X.XXX -" prefix
    clean_html_title = re.sub(r'Ley\s+[\d\.]+\s*-\s*', '', html_title, flags=re.IGNORECASE)
    
    def get_significant_words(s):
        norm = normalize_string(s)
        words = set(norm.split())
        return {w for w in words if w not in stopwords and len(w) > 2}

    html_words = get_significant_words(clean_html_title)
    json_words = get_significant_words(json_title)
    
    # If we have significant words in HTML title, check if they exist in JSON
    if html_words:
        common = html_words.intersection(json_words)
        
        # If overlap is low (e.g. less than 50% of significant HTML words are found in JSON)
        # We use a relatively strict threshold because titles should be similar.
        match_ratio = len(common) / len(html_words)
        
        if match_ratio < 0.5:
            # Construct a snippet of significant words for debugging
            issues.append(
                f"Title Mismatch: HTML says '{html_title}' but JSON says '{json_title}'. "
                f"Significant words mismatch (Found {len(common)}/{len(html_words)} matches: {common}). "
                f"Please verify this is the correct law."
            )
            
    return issues

def validate_law_logic(law_id, data):
    """
    Performs logical checks on the Law JSON structure.
    Returns list of issues (strings).
    """
    issues = []
    ley = data.get("ley", {})
    titulos = ley.get("titulos", [])
    
    seen_articles = defaultdict(list) # number -> list of locations (Title names)
    
    for titulo in titulos:
        t_nombre = titulo.get("nombre", "Unknown Title")
        articulos = titulo.get("articulos", [])
        
        for art in articulos:
            art_num = art.get("numero")
            if not art_num:
                continue
            
            # Check 1: Duplicate Articles
            seen_articles[art_num].append(t_nombre)
            
            # Check 2: Suspicious Partial Substitution
            # If action is 'sustitúyese' (implies full replacement) but text starts with a list marker like 'c)'
            accion = art.get("accion", "").lower()
            texto_nuevo = art.get("texto_nuevo", "")
            
            if "sustitúyese" in accion and texto_nuevo:
                # Regex for starting with "a)", "1.", "c)", etc.
                if re.match(r'^\s*[a-z0-9]{1,2}\)\s+', texto_nuevo):
                     issues.append(
                        f"Suspicious Substitution in Art {art_num}: Action is '{accion}' but new text starts with list marker (e.g. 'a)'). "
                        "This might be a partial replacement labeled incorrectly."
                    )

    # Report duplicates
    for art_num, locations in seen_articles.items():
        if len(locations) > 1:
            issues.append(
                f"Duplicate Article {art_num} found in {len(locations)} titles: {', '.join(locations[:3])}..."
            )
            
    return issues

def validate_law_data(law_id, html_title):
    """Validates the JSON file for a specific law, including logic and consistency."""
    filename = f"comparacion_global_ley_{law_id}.json"
    fpath = DATA_DIR / filename
    
    if not fpath.exists():
        logger.error(f"[{law_id}] Missing data file: {filename}")
        return False
    
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Schema check
        if "ley" not in data:
            logger.error(f"[{law_id}] Invalid schema: missing 'ley' key")
            return False
            
        if "titulos" not in data["ley"]:
             logger.error(f"[{law_id}] Invalid schema: missing 'ley.titulos'")
             return False

        # Logical & Consistency Checks
        issues = []
        issues.extend(check_title_consistency(law_id, html_title, data))
        issues.extend(validate_law_logic(law_id, data))
        
        if issues:
            logger.warning(f"[{law_id}] Issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            # We treat these as warnings for now, but could be errors if strict
            return True # Returning True because file exists and is parsable, issues are logged
             
        logger.debug(f"[{law_id}] Valid.")
        return True
        
    except json.JSONDecodeError:
        logger.error(f"[{law_id}] Invalid JSON syntax in {filename}")
        return False
    except Exception as e:
        logger.error(f"[{law_id}] Error reading {filename}: {e}")
        return False

def main():
    logger.info("Starting Site QA...")
    
    if not DOCS_DIR.exists():
        logger.critical(f"Directory {DOCS_DIR} not found.")
        sys.exit(1)

    # 1. Check Core Files
    if not check_core_files():
        sys.exit(1)

    # 2. Get Laws from HTML
    laws_dict = get_referenced_laws_with_titles()
    if not laws_dict:
        logger.error("No laws found to check. Aborting.")
        sys.exit(1)

    # 3. Validate Data
    errors = 0
    checked_files = set()
    
    for law_id, law_title in laws_dict.items():
        if validate_law_data(law_id, law_title):
            checked_files.add(f"comparacion_global_ley_{law_id}.json")
        else:
            errors += 1
            
    # 4. Check for Unused Data Files
    all_json_files = {f.name for f in DATA_DIR.glob("*.json") if f.name.startswith("comparacion_global_")}
    unused_files = all_json_files - checked_files
    
    if unused_files:
        logger.warning(f"Found {len(unused_files)} unused data files (not referenced in index.html):")
        for f in sorted(unused_files):
            logger.warning(f"  - {f}")

    if errors > 0:
        logger.error(f"QA Failed: {errors} critical errors found.")
        sys.exit(1)
    
    logger.info("QA Passed: Site integrity verified (check warnings above for logical issues).")
    sys.exit(0)

if __name__ == "__main__":
    main()
