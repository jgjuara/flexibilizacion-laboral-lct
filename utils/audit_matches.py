import json
import glob
import os
import sys
import re

def audit():
    print("Starting Audit...")
    
    # 1. Load all Dictamen Operations
    all_operations = []
    files = glob.glob("data/dictamen_modernizacion_laboral_titulo_*.json")
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                item['_source_file'] = os.path.basename(file_path)
                all_operations.append(item)
                
    mismatches = []
    
    # Check for UNKNOWN laws
    for op in all_operations:
        header = op.get("encabezado", "").lower()
        
        # SKIP: "Créase" or "Incorpórase" without explicit target often means new regime
        if op.get("ley_numero") == "UNKNOWN" or not op.get("ley_numero"):
            if "créase" in header or "crease" in header:
                continue # Ignore New Regimes
            
            # Check for "De forma" articles (usually the last ones)
            if "de forma" in header or "comuníquese" in header:
                continue

            mismatches.append({
                "type": "UNKNOWN_LAW",
                "dictamen_articulo": op.get("dictamen_articulo"),
                "encabezado": op.get("encabezado"),
                "source_file": op.get("_source_file")
            })

    # Group operations by law
    ops_by_law = {}
    for op in all_operations:
        ley = op.get("ley_numero")
        if ley and ley != "UNKNOWN":
            ley = str(ley).replace(".", "").strip()
            if ley not in ops_by_law:
                ops_by_law[ley] = []
            ops_by_law[ley].append(op)
            
    # Check against generated comparison files
    for law_id, ops in ops_by_law.items():
        comp_file = f"data/comparacion_global_ley_{law_id}.json"
        
        if not os.path.exists(comp_file):
            # If file missing, check if it's a STUB (we just created them, maybe matcher hasn't run yet)
            # But normally matcher SHOULD generate the file even for stubs.
            for op in ops:
                mismatches.append({
                    "type": "LAW_FILE_MISSING",
                    "law_id": law_id,
                    "dictamen_articulo": op.get("dictamen_articulo"),
                    "encabezado": op.get("encabezado"),
                    "source_file": op.get("_source_file")
                })
            continue
            
        with open(comp_file, 'r', encoding='utf-8') as f:
            comp_data = json.load(f)
            
        # Collect matched dictamen articles from the output structure
        matched_dictamen_ids = set()
        
        # Check metadata for global/chapter derogations
        derogacion_total = comp_data.get("metadatos", {}).get("derogacion_total", False)
        capitulos_derogados = set(comp_data.get("metadatos", {}).get("capitulos_derogados", []))
        
        def traverse(node):
            if isinstance(node, dict):
                if "dictamen_articulo" in node and node["dictamen_articulo"]:
                    matched_dictamen_ids.add(str(node["dictamen_articulo"]))
                for k, v in node.items():
                    traverse(v)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
                    
        traverse(comp_data)
        
        # Verify
        for op in ops:
            d_id = str(op.get("dictamen_articulo"))
            header = op.get("encabezado", "").lower()
            accion = op.get("accion", "").lower()
            target_cap = op.get("destino_capitulo")
            
            # 1. Direct Match in Output Tree
            if d_id in matched_dictamen_ids:
                continue

            # 2. Whole Law Derogation Match
            if derogacion_total and "derógase" in accion:
                continue
                
            # 3. Chapter Derogation Match
            if target_cap and str(target_cap) in capitulos_derogados:
                continue

            # 4. Fallback: Header Text Heuristics (for safety)
            if "derógase la ley" in header or "derogase la ley" in header or \
               "derógase el decreto ley" in header or "derogase el decreto ley" in header:
                continue

            mismatches.append({
                "type": "ARTICLE_NOT_FOUND_IN_LAW",
                "law_id": law_id,
                "target_article": op.get("destino_articulo") or op.get("destino_capitulo"),
                "dictamen_articulo": d_id,
                "encabezado": op.get("encabezado"),
                "source_file": op.get("_source_file")
            })

    # Save Report
    with open("data/audit_report_mismatches.json", "w", encoding='utf-8') as f:
        json.dump(mismatches, f, ensure_ascii=False, indent=2)
        
    print(f"Audit Complete. Found {len(mismatches)} issues.")
    print("Report saved to data/audit_report_mismatches.json")

if __name__ == "__main__":
    audit()