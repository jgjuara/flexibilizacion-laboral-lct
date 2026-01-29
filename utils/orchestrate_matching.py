import json
import glob
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.comparar_ley_dictamen import comparar_ley_dictamen_objects

def orchestrate():
    # 1. Aggregate Dictamen Articles
    print("Aggregating Dictamen Articles...")
    articles_by_law: Dict[str, List[Dict[str, Any]]] = {}
    
    files = glob.glob("data/dictamen_modernizacion_laboral_titulo_*.json")
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                ley = item.get("ley_numero")
                if ley and ley != "UNKNOWN":
                    # Normalize law number (remove dots)
                    ley_clean = str(ley).replace(".", "").strip()
                    if ley_clean not in articles_by_law:
                        articles_by_law[ley_clean] = []
                    articles_by_law[ley_clean].append(item)

    print(f"Found operations for {len(articles_by_law)} unique laws.")

    # 2. Process each Law
    for law_id, operations in articles_by_law.items():
        normalized_law_path = f"data/normalized_ley_{law_id}.json"
        
        if not os.path.exists(normalized_law_path):
            print(f"Skipping Law {law_id}: Normalized file not found.")
            continue
            
        print(f"Processing Law {law_id} ({len(operations)} operations)...")
        
        try:
            with open(normalized_law_path, 'r', encoding='utf-8') as f:
                ley_data = json.load(f)
                
            comparacion = comparar_ley_dictamen_objects(
                ley_data,
                operations,
                ley_source_name=f"normalized_ley_{law_id}.json",
                dictamen_source_name="aggregated_dictamen"
            )
            
            output_path = f"data/comparacion_global_ley_{law_id}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(comparacion, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error processing Law {law_id}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    orchestrate()
