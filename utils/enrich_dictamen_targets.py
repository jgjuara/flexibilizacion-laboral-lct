import json
import re
import glob
import os
from typing import Dict, List, Optional, Any

# Mapping of keywords/phrases to Law Numbers
# Derived from leyes_modificadas_dictamen.json and common legal text usage
LAW_MAPPING = {
    r"ley de contrato de trabajo": "20744",
    r"ley de contrato de": "20744", # Truncated header support
    r"l\.c\.t\.": "20744",
    
    r"ley de organización y": "18345", # Ley 18.345 Proc. Laboral
    r"ley de honorarios": "27423", # Ley 27.423 Honorarios
    
    r"ley nacional de empleo": "24013",
    r"ley N° 24\.013": "24013",
    
    r"jornada de trabajo": "11544",
    r"ley N° 11\.544": "11544",
    
    r"riesgos del trabajo": "24557",
    r"ley N° 24\.557": "24557",
    
    r"asociaciones sindicales": "23551",
    r"ley N° 23\.551": "23551",
    
    r"convenciones colectivas": "14250",
    r"ley N° 14\.250": "14250",
    
    r"empleo no registrado": "25323",
    r"ley N° 25\.323": "25323",
    
    r"teletrabajo": "27555",
    r"ley N° 27\.555": "27555",
    
    r"régimen nacional de trabajo agrario": "26727",
    r"ley N° 26\.727": "26727",
    
    r"casas particulares": "26844",
    r"ley N° 26\.844": "26844",
    
    r"pyme": "24467",
    r"ley N° 24\.467": "24467",
    
    r"sistema integrado de jubilaciones": "24241",
    r"ley N° 24\.241": "24241",
    
    r"ley N° 25\.212": "25212", # Pacto federal trabajo
    r"ley N° 17\.250": "17250",
    r"ley N° 12\.713": "12713", # Trabajo a domicilio
    r"ley N° 12\.908": "12908", # Periodistas
    r"ley N° 14\.546": "14546", # Viajantes
    r"ley N° 14\.786": "14786", # Conciliacion obligatoria
    r"ley N° 23\.546": "23546", # Procedimiento paritarias
    r"ley N° 24\.156": "24156", # Admin financiera (sector publico)
    r"ley N° 25\.674": "25674", # Cupo femenino sindical
    r"ley N° 25\.877": "25877", # Ordenamiento laboral
    r"ley N° 26\.590": "26590", # Cuentas sueldo
    r"ley N° 27\.423": "27423", # Honorarios
    r"ley N° 27\.553": "27553", # Recetas electronicas
    r"ley N° 23\.079": "23079",
    r"ley N° 23\.472": "23472",
    r"ley N° 23\.759": "23759",
    r"ley N° 24\.493": "24493",
    r"ley N° 24\.714": "24714",
    r"ley N° 12\.867": "12867",
    r"ley N° 13\.839": "13839",
    r"ley N° 14\.954": "14954",
    r"ley N° 20\.657": "20657",
}

def detect_law(encabezado: str) -> Optional[str]:
    """Detects the law number from the article header."""
    if not encabezado:
        return None
        
    encabezado_lower = encabezado.lower()
    
    # Check explicitly defined patterns
    for pattern, law_num in LAW_MAPPING.items():
        if re.search(pattern, encabezado_lower, re.IGNORECASE):
            return law_num
            
    # Fallback: regex for "Ley N° X.XXX" or "Ley X.XXX"
    # Matches "Ley N° 12.345", "Ley 12345", "Ley Nº 12.345"
    match = re.search(r"ley (?:n[°º\.]?\s*)?(\d{1,3}(?:\.?\d{3})*)", encabezado_lower)
    if match:
        number = match.group(1).replace(".", "")
        if len(number) >= 4: # Filter out short numbers that might be article numbers
            return number
            
    # Fallback for "Decreto Ley" or "Decreto-Ley"
    match_dl = re.search(r"decreto[\s-]ley (?:n[°º\.]?\s*)?(\d{1,3}(?:\.?\d{3})*)", encabezado_lower)
    if match_dl:
        number = match_dl.group(1).replace(".", "")
        return number
            
    return None

def fix_article_targets(item: Dict[str, Any]) -> bool:
    """
    Intenta corregir el artículo destino basándose en el encabezado.
    Retorna True si hubo cambios.
    """
    encabezado = item.get("encabezado", "")
    if not encabezado:
        return False
        
    # 1. Buscar patrón de lista de artículos: "los artículos 10, 16 y 21"
    match_list = re.search(
        r"(?:sustit|der[oó]g|modif)[^ ]*\s+los\s+art[íi]culos\s+([\d\s,y°ºº°bis\-]+)",
        encabezado,
        re.IGNORECASE
    )
    if match_list:
        raw_list = match_list.group(1).strip()
        # Limpiar y normalizar la lista
        # Ej: "10, 16 y 21" -> "10, 16, 21"
        clean_list = re.sub(r"\s+y\s+", ", ", raw_list, flags=re.IGNORECASE)
        # Quitar ordinales
        clean_list = re.sub(r"\s*[°º]", "", clean_list)
        
        current_target = item.get("destino_articulo")
        if str(clean_list) != str(current_target):
            item["destino_articulo"] = clean_list
            return True

    # 2. Buscar patrón de artículo único: "el artículo X"
    match_single = re.search(
        r"(?:sustit|der[oó]g|modif|incorp)[^ ]*\s+(?:el|los|como\s+|inciso\s+\w+\s+al\s+)?\s*art[íi]culo[s]?\s+(\d+(?:\s*[°º])?(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)",
        encabezado,
        re.IGNORECASE
    )
    
    if match_single:
        extracted_target = match_single.group(1).strip()
        # Normalizar: quitar °/º para consistencia en la búsqueda
        extracted_target = re.sub(r"\s*[°º]", "", extracted_target)
        
        current_target = item.get("destino_articulo")
        
        # Normalizar para comparar (quitar espacios, puntos)
        def norm(s): return str(s).lower().replace(" ", "").replace(".", "") if s else ""
        
        if norm(extracted_target) != norm(current_target):
            item["destino_articulo"] = extracted_target
            return True
            
    return False

def enrich_files():
    # Load Heuristics
    heuristics = {
        "manual_matches": [],
        "law_replacements": {},
        "null_target_overrides": []
    }
    if os.path.exists("data/matching_heuristics.json"):
        with open("data/matching_heuristics.json", "r", encoding='utf-8') as f:
            heuristics = json.load(f)
            print(f"Loaded heuristics file.")

    # Index manual matches for faster lookup
    manual_matches_map = {item["dictamen_articulo"]: item for item in heuristics.get("manual_matches", [])}
    law_replacements = heuristics.get("law_replacements", {})
    null_target_overrides = set(heuristics.get("null_target_overrides", []))

    files = glob.glob("data/dictamen_modernizacion_laboral_titulo_*.json")
    print(f"Found {len(files)} dictamen files to process.")
    
    unknown_count = 0
    enriched_count = 0
    
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        modified = False
        for item in data:
            art_id = str(item.get("dictamen_articulo"))
            
            # 1. Apply Law Replacements (Correction of wrong law detection)
            if art_id in law_replacements:
                item["ley_numero"] = law_replacements[art_id]
                modified = True
                enriched_count += 1

            # 2. Apply Manual Matches (Specific Target Mapping)
            if art_id in manual_matches_map:
                match_data = manual_matches_map[art_id]
                if "target_ley" in match_data:
                    item["ley_numero"] = match_data["target_ley"]
                if "target_articulo" in match_data:
                    item["destino_articulo"] = match_data["target_articulo"]
                modified = True
                enriched_count += 1
                continue # Skip further auto-detection for manually matched items
            
            # 3. Apply Null Target Overrides (Force target to null for whole-law derogations)
            if art_id in null_target_overrides:
                item["destino_articulo"] = None
                item["destino_inciso"] = None
                item["destino_capitulo"] = None
                modified = True
                enriched_count += 1
                continue # Skip further detection

            # 4. Standard Law Detection (only if missing or UNKNOWN)
            current_ley = item.get("ley_numero")
            if not current_ley or current_ley == "UNKNOWN":
                detected = detect_law(item.get("encabezado", ""))
                
                if detected:
                    item["ley_numero"] = detected
                    enriched_count += 1
                    modified = True
                else:
                    item["ley_numero"] = "UNKNOWN"
                    unknown_count += 1
                    modified = True
            
            # 5. Fix Article Targets (Correction of bad parsing)
            # Run this AFTER law detection but BEFORE saving
            if fix_article_targets(item):
                modified = True
                enriched_count += 1
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
    print(f"Enrichment Complete.")
    print(f"  - Articles Enriched: {enriched_count}")
    print(f"  - Unknown Laws: {unknown_count}")

if __name__ == "__main__":
    enrich_files()
