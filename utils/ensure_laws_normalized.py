import json
import glob
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path to import local modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_required_laws():
    """Scans all dictamen files to find unique law numbers."""
    laws = set()
    files = glob.glob("data/dictamen_modernizacion_laboral_titulo_*.json")
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                ley = item.get("ley_numero")
                if ley and ley != "UNKNOWN":
                    # Normalize: remove dots, strip
                    ley = str(ley).replace(".", "").strip()
                    if ley.isdigit():
                        laws.add(ley)
    return sorted(list(laws))

def normalize_law(law_num, raw_file):
    """Runs the parser on a raw law file."""
    output_file = f"data/normalized_ley_{law_num}.json"
    if os.path.exists(output_file):
        # Already normalized
        return
    
    print(f"Normalizing Law {law_num} from {raw_file}...")
    cmd = [
        "uv", "run", "parsers/saij/parser.py",
        raw_file,
        "-o", output_file
    ]
    subprocess.run(cmd, check=True)

def ensure_laws():
    required_laws = get_required_laws()
    print(f"Required Laws: {required_laws}")
    
    for law_num in required_laws:
        # Check if normalized exists
        if os.path.exists(f"data/normalized_ley_{law_num}.json"):
            continue
            
        # Check if raw exists (format: [NUM]-*.json)
        raw_files = glob.glob(f"data/{law_num}-*.json")
        
        if raw_files:
            # Use the first one found
            normalize_law(law_num, raw_files[0])
        else:
            print(f"Law {law_num} missing. Scraping...")
            # Run scraper
            # We use saij-data/scraper.py directly via uv run
            cmd = ["uv", "run", "saij-data/scraper.py", law_num, "--directorio", "data"]
            try:
                subprocess.run(cmd, check=True)
                # Find the file again
                raw_files = glob.glob(f"data/{law_num}-*.json")
                if raw_files:
                    normalize_law(law_num, raw_files[0])
                else:
                    print(f"Error: Scraper ran but no file found for {law_num}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to scrape law {law_num}: {e}")

if __name__ == "__main__":
    ensure_laws()
