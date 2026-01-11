#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser de "dictámenes" que modifican normas (ej. LCT) donde aparecen
dos niveles de "ARTÍCULO": (a) artículo del dictamen (operación) y
(b) artículo/inciso del texto que se incorpora a la ley.

Estrategia (parser por estados):
- Detecta encabezados "ARTÍCULO N°-" (posible artículo del dictamen).
- Clasifica como "dictamen" si el encabezado (o la línea siguiente) contiene verbos operativos:
  Sustitúyese / Incorpórase / Derógase / Modifícase / etc.
- Si encuentra gatillos "por el siguiente:" / "el siguiente texto:" empieza a capturar el texto nuevo
  hasta el próximo artículo del dictamen o un encabezado estructural (TÍTULO/CAPÍTULO/SECCIÓN).

Salida: JSON con una lista de operaciones (artículos del dictamen) y su texto nuevo, si aplica.

Requisitos:
  - pdfplumber (recomendado) o PyMuPDF (fitz) como fallback.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple


# ----------------------------
# Config / patrones
# ----------------------------

HEADER_RE = re.compile(
    r"^\s*ART[ÍI]CULO\s+([0-9]+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?\s*[-–—]\s*(.*)\s*$",
    re.IGNORECASE,
)

# Encabezados estructurales típicos que delimitan bloques
STRUCT_RE = re.compile(r"^\s*(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|ANEXO)\b", re.IGNORECASE)

# Patrón para detectar títulos con número (TÍTULO I, TÍTULO II, etc.)
# Busca al inicio de línea o después de un salto de línea implícito
TITULO_RE = re.compile(r"^\s*T[ÍI]TULO\s+([IVXLCDM]+|[0-9]+)\b", re.IGNORECASE)
# También buscar en medio de línea por si acaso
TITULO_RE_ANYWHERE = re.compile(r"\bT[ÍI]TULO\s+([IVXLCDM]+|[0-9]+)\b", re.IGNORECASE)

# Verbos operativos típicos del dictamen (operaciones legislativas)
OP_VERBS = [
    "sustitúyese", "sustituyese",
    "incorpórase", "incorporase",
    "derógase", "derogase",
    "modifícase", "modificase",
    "créase", "crease",
    "suprímese", "suprimese",
    "reemplázase", "reemplazase",
]

OP_VERB_RE = re.compile(r"\b(" + "|".join(map(re.escape, OP_VERBS)) + r")\b", re.IGNORECASE)

# Gatillos que indican el inicio del "texto nuevo"
TRIGGER_RE = re.compile(
    r"(por\s+el\s+siguiente\s*:|el\s+siguiente\s+texto\s*:|por\s+el\s+siguiente\s+texto\s*:|por\s+el\s+siguiente\s*:)",
    re.IGNORECASE,
)

# Regex específico para incorporaciones (prioridad alta)
INCORPORATION_TARGET_RE = re.compile(
    r"incorp[óo]rase\s+como\s+art[íi]culo\s+([0-9]+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?",
    re.IGNORECASE
)

# Extracción simple de destino (fallback)
TARGET_ART_RE = re.compile(
    r"art[íi]culo\s+([0-9]+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?",
    re.IGNORECASE
)

# Regex específico para buscar "el artículo X" después del verbo operativo
# Esto evita capturar el número del artículo del dictamen (ej: "ARTÍCULO 21-")
TARGET_ART_AFTER_VERB_RE = re.compile(
    r"(?:sustit[úu]yese|der[óo]gase|modif[íi]case|supr[íi]mese|reempl[áa]zase)\s+el\s+art[íi]culo\s+([0-9]+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?",
    re.IGNORECASE
)
TARGET_INCISO_RE = re.compile(r"inciso\s+([a-z])\)\s+del\s+art[íi]culo\s+([0-9]+)\s*[°º]?", re.IGNORECASE)

# Regex para detectar derogaciones de capítulos completos
TARGET_CAPITULO_RE = re.compile(r"der[óo]gase\s+el\s+cap[íi]tulo\s+([IVXLCDM]+|[0-9]+)", re.IGNORECASE)

LAW_NUM_RE = re.compile(r"Ley\s+.*?N[°º]\s*([0-9\.\-]+)", re.IGNORECASE)


# ----------------------------
# Modelo de salida
# ----------------------------

@dataclass
class Operation:
    dictamen_articulo: str
    encabezado: str
    accion: Optional[str] = None
    ley_numero: Optional[str] = None
    destino_articulo: Optional[str] = None
    destino_inciso: Optional[str] = None
    destino_articulo_padre: Optional[str] = None  # si destino_inciso aplica, acá va el artículo padre
    destino_capitulo: Optional[str] = None  # si se deroga un capítulo completo
    texto_nuevo: Optional[str] = None
    texto_nuevo_lineas: Optional[List[str]] = None


# ----------------------------
# Extracción de texto desde PDF
# ----------------------------

def extract_lines_from_pdf(pdf_path: str) -> List[str]:
    """
    Devuelve líneas de texto (una lista de strings), preservando el orden del PDF.
    Intenta pdfplumber; si no, usa PyMuPDF (fitz).
    """
    try:
        import pdfplumber  # type: ignore
        lines: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                page_lines = txt.splitlines()
                lines.extend(page_lines)
        return lines
    except Exception:
        # Fallback: PyMuPDF
        try:
            import fitz  # type: ignore
            doc = fitz.open(pdf_path)
            lines = []
            for page in doc:
                txt = page.get_text("text") or ""
                lines.extend(txt.splitlines())
            return lines
        except Exception as e:
            raise RuntimeError(
                "No pude extraer texto del PDF. Instala 'pdfplumber' o 'pymupdf'."
            ) from e


# ----------------------------
# Limpieza / normalización
# ----------------------------

def _is_probable_footer_header(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # heurísticas simples; ajustar si el PDF tiene otros patrones
    if re.search(r"^\s*p[áa]gina\s+\d+", s, re.IGNORECASE):
        return True
    if re.search(r"^\s*\d+\s*$", s):  # solo número
        return True
    return False


def normalize_lines(raw_lines: List[str]) -> List[str]:
    """
    - Elimina encabezados/pies evidentes.
    - Une cortes por guión al final de línea (palabra partida).
    - Colapsa espacios.
    """
    # Filtrar basura obvia
    filtered = [ln for ln in raw_lines if not _is_probable_footer_header(ln)]

    # Normalizar espacios
    filtered = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in filtered]

    # Unir palabras partidas por guión al final de línea: "contra-\n to" -> "contrato"
    joined: List[str] = []
    i = 0
    while i < len(filtered):
        line = filtered[i]
        if line.endswith("-") and i + 1 < len(filtered):
            nxt = filtered[i + 1].lstrip()
            # Si la siguiente línea comienza con letra, asumimos partición de palabra
            if nxt and nxt[0].isalpha():
                joined.append(line[:-1] + nxt)
                i += 2
                continue
        joined.append(line)
        i += 1

    return joined


# ----------------------------
# Detección de "artículo del dictamen"
# ----------------------------

def looks_like_dictamen_header(header_tail: str) -> bool:
    """
    Devuelve True si el contenido del encabezado sugiere operación legislativa.
    """
    return bool(OP_VERB_RE.search(header_tail or ""))


def find_next_nonempty(lines: List[str], start: int) -> Tuple[int, str]:
    j = start
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return j, ""
    return j, lines[j]


def is_dictamen_header(lines: List[str], idx: int) -> Tuple[bool, str, int]:
    """
    Decide si lines[idx] es un encabezado de artículo DEL DICTAMEN.
    Retorna:
      (es_dictamen, encabezado_completo, idx_siguiente)
    donde idx_siguiente permite "consumir" una línea adicional si el verbo operativo viene en la línea siguiente.
    """
    m = HEADER_RE.match(lines[idx])
    if not m:
        return (False, "", idx + 1)

    art_num = m.group(1).strip()
    tail = (m.group(2) or "").strip()

    if looks_like_dictamen_header(tail):
        return (True, f"ARTÍCULO {art_num}- {tail}".strip(), idx + 1)

    # Caso: "ARTÍCULO N°-" y el verbo viene en la línea siguiente
    j, nxt = find_next_nonempty(lines, idx + 1)
    if nxt and looks_like_dictamen_header(nxt):
        # "unimos" esa línea al encabezado
        combined = f"ARTÍCULO {art_num}- {nxt.strip()}"
        return (True, combined, j + 1)

    return (False, "", idx + 1)


def parse_action_and_target(header_text: str) -> Dict[str, Optional[str]]:
    """
    Extrae campos básicos de la operación:
      - accion (verbo operativo)
      - ley_numero
      - destino_articulo, destino_inciso, destino_articulo_padre, destino_capitulo
    """
    out: Dict[str, Optional[str]] = {
        "accion": None,
        "ley_numero": None,
        "destino_articulo": None,
        "destino_inciso": None,
        "destino_articulo_padre": None,
        "destino_capitulo": None,
    }

    mv = OP_VERB_RE.search(header_text)
    if mv:
        out["accion"] = mv.group(1).lower()

    mlaw = LAW_NUM_RE.search(header_text)
    if mlaw:
        out["ley_numero"] = mlaw.group(1)

    # Para derogaciones, buscar primero si se deroga un capítulo completo
    if out["accion"] == "derógase" or out["accion"] == "derogase":
        mcap = TARGET_CAPITULO_RE.search(header_text)
        if mcap:
            out["destino_capitulo"] = mcap.group(1).strip()
            return out

    minc = TARGET_INCISO_RE.search(header_text)
    if minc:
        out["destino_inciso"] = f"{minc.group(1)})"
        out["destino_articulo_padre"] = minc.group(2)
        return out

    # Para incorporaciones, buscar primero el patrón específico
    if out["accion"] == "incorpórase" or out["accion"] == "incorporase":
        mincorp = INCORPORATION_TARGET_RE.search(header_text)
        if mincorp:
            out["destino_articulo"] = mincorp.group(1).strip()
            return out

    # Para sustituciones/derogaciones/modificaciones, buscar "el artículo X" después del verbo
    # Esto evita capturar el número del artículo del dictamen (ej: "ARTÍCULO 21-")
    if out["accion"] in ("sustitúyese", "sustituyese", "derógase", "derogase", "modifícase", "modificase", "suprímese", "suprimese", "reemplázase", "reemplazase"):
        mart_after_verb = TARGET_ART_AFTER_VERB_RE.search(header_text)
        if mart_after_verb:
            out["destino_articulo"] = mart_after_verb.group(1).strip()
            return out

    # Fallback: buscar cualquier "artículo X" (puede ser incorrecto si coincide con el número del dictamen)
    mart = TARGET_ART_RE.search(header_text)
    if mart:
        out["destino_articulo"] = mart.group(1).strip()

    return out


def extract_article_number_from_texto_nuevo(texto_nuevo: str) -> Optional[str]:
    """
    Extrae el número de artículo desde el inicio de texto_nuevo.
    
    Patrones esperados:
    - "ARTÍCULO 2°-"
    - "ARTÍCULO 4°-"
    - "ARTÍCULO 11-"
    - "ARTÍCULO 11 bis-"
    
    Esta es la fuente de verdad para destino_articulo, ya que el texto_nuevo
    siempre contiene el artículo correcto que se está modificando.
    """
    if not texto_nuevo:
        return None
    
    # Patrón para extraer número de artículo (puede incluir bis, ter, quater, etc.)
    # Acepta tanto guion (-) como punto (.) después del número
    pattern = r"ART[ÍI]CULO\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?[\.-]"
    match = re.search(pattern, texto_nuevo, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return None


# ----------------------------
# Parser principal
# ----------------------------

def parse_dictamen(lines: List[str]) -> Dict[str, List[Operation]]:
    """
    Parsea el dictamen y agrupa las operaciones por título.
    Retorna un diccionario donde las claves son los números de título (I, II, etc.)
    y los valores son listas de operaciones.
    """
    titulos_ops: Dict[str, List[Operation]] = {}
    current_titulo: Optional[str] = None
    i = 0

    current: Optional[Operation] = None
    capturing_new_text = False
    new_text_lines: List[str] = []
    
    def get_current_ops() -> List[Operation]:
        """Obtiene la lista de operaciones del título actual, creándola si no existe."""
        nonlocal current_titulo
        if current_titulo is None:
            current_titulo = "SIN_TITULO"
        if current_titulo not in titulos_ops:
            titulos_ops[current_titulo] = []
        return titulos_ops[current_titulo]

    while i < len(lines):
        line = lines[i]

        # Detectar inicio de nuevo título (primero al inicio de línea, luego en cualquier parte)
        titulo_match = TITULO_RE.match(line)
        if not titulo_match:
            # Fallback: buscar en cualquier parte de la línea
            titulo_match = TITULO_RE_ANYWHERE.search(line)
        
        if titulo_match:
            # Si hay una operación en curso, cerrarla antes de cambiar de título
            if current:
                if capturing_new_text:
                    current.texto_nuevo_lineas = new_text_lines[:] if new_text_lines else None
                    current.texto_nuevo = "\n".join(new_text_lines).strip() if new_text_lines else None
                    if current.texto_nuevo:
                        extracted_article = extract_article_number_from_texto_nuevo(current.texto_nuevo)
                        if extracted_article:
                            current.destino_articulo = extracted_article
                # Agregar al título actual
                get_current_ops().append(current)
                current = None
                capturing_new_text = False
                new_text_lines = []
            
            # Iniciar nuevo título
            current_titulo = titulo_match.group(1).strip()
            # Inicializar la lista para el nuevo título
            if current_titulo not in titulos_ops:
                titulos_ops[current_titulo] = []
            
            i += 1
            continue

        # Delimitadores fuertes: encabezados estructurales (excepto títulos que ya manejamos)
        if STRUCT_RE.match(line) and current and capturing_new_text:
            # Si es un título, ya lo manejamos arriba
            if not TITULO_RE.match(line):
                # cerrar captura
                current.texto_nuevo_lineas = new_text_lines[:] if new_text_lines else None
                current.texto_nuevo = "\n".join(new_text_lines).strip() if new_text_lines else None
                # Extraer destino_articulo desde texto_nuevo si está disponible
                if current.texto_nuevo:
                    extracted_article = extract_article_number_from_texto_nuevo(current.texto_nuevo)
                    if extracted_article:
                        current.destino_articulo = extracted_article
                # Agregar al título actual
                get_current_ops().append(current)
                current = None
                capturing_new_text = False
                new_text_lines = []
            # no consumimos el struct; simplemente avanzamos
            i += 1
            continue

        # ¿Es un encabezado de artículo?
        if HEADER_RE.match(line):
            # Si es encabezado, decidir si es "artículo del dictamen"
            is_dic, full_header, next_i = is_dictamen_header(lines, i)

            if is_dic:
                # Si veníamos capturando texto nuevo, cerramos la operación anterior
                if current:
                    if capturing_new_text:
                        current.texto_nuevo_lineas = new_text_lines[:] if new_text_lines else None
                        current.texto_nuevo = "\n".join(new_text_lines).strip() if new_text_lines else None
                        # Extraer destino_articulo desde texto_nuevo si está disponible
                        if current.texto_nuevo:
                            extracted_article = extract_article_number_from_texto_nuevo(current.texto_nuevo)
                            if extracted_article:
                                current.destino_articulo = extracted_article
                    # Agregar al título actual
                    get_current_ops().append(current)

                # Iniciar nueva operación
                m = HEADER_RE.match(line)
                assert m is not None
                dictamen_art = m.group(1).strip()

                meta = parse_action_and_target(full_header)
                current = Operation(
                    dictamen_articulo=dictamen_art,
                    encabezado=full_header.strip(),
                    accion=meta["accion"],
                    ley_numero=meta["ley_numero"],
                    destino_articulo=meta["destino_articulo"],
                    destino_inciso=meta["destino_inciso"],
                    destino_articulo_padre=meta["destino_articulo_padre"],
                    destino_capitulo=meta["destino_capitulo"],
                )
                capturing_new_text = False
                new_text_lines = []
                i = next_i
                continue

            # Si NO es dictamen header: es muy probable que sea encabezado del texto nuevo (de la ley)
            # En ese caso lo tratamos como una línea más dentro del texto nuevo, si estamos capturando.
            if current and capturing_new_text:
                if line.strip():
                    new_text_lines.append(line.strip())
                i += 1
                continue

        # Si hay operación en curso, buscamos gatillo para iniciar captura
        if current and not capturing_new_text:
            mt = TRIGGER_RE.search(line)
            if mt:
                capturing_new_text = True

                # Si hubiera texto después del gatillo en la misma línea, lo incorporamos
                after = line[mt.end():].strip()
                if after:
                    new_text_lines.append(after)
                i += 1
                continue
            
            # Para incorporaciones, si no hay gatillo, buscar inicio automático
            # Detectar cuando una línea comienza con "ARTÍCULO" como indicador
            if current.accion == "incorpórase" or current.accion == "incorporase":
                # Si la línea comienza con "ARTÍCULO", es probable que sea el inicio del texto nuevo
                if HEADER_RE.match(line.strip()):
                    capturing_new_text = True
                    if line.strip():
                        new_text_lines.append(line.strip())
                    i += 1
                    continue
                # También considerar líneas no vacías después del encabezado como posible inicio
                # (solo si no hemos encontrado un gatillo en las primeras líneas)
                elif line.strip() and i < len(lines) - 1:
                    # Verificar si la siguiente línea parece ser parte del texto nuevo
                    # (contiene texto sustancial, no solo números o encabezados estructurales)
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if next_line and not STRUCT_RE.match(next_line) and not TITULO_RE.match(next_line):
                        # Si la línea actual parece ser texto (no es solo un número o encabezado)
                        if not re.match(r"^\s*\d+\s*$", line.strip()) and not HEADER_RE.match(line.strip()):
                            capturing_new_text = True
                            new_text_lines.append(line.strip())
                            i += 1
                            continue

        # Si estamos capturando el texto nuevo, acumulamos líneas (ignorando vacíos redundantes)
        if current and capturing_new_text:
            s = line.strip()
            if s:
                new_text_lines.append(s)
            else:
                # mantener un blanco moderado: solo si el último no es blanco
                if new_text_lines and new_text_lines[-1] != "":
                    new_text_lines.append("")
            i += 1
            continue

        i += 1

    # Cierre final
    if current:
        if capturing_new_text:
            current.texto_nuevo_lineas = new_text_lines[:] if new_text_lines else None
            current.texto_nuevo = "\n".join(new_text_lines).strip() if new_text_lines else None
            # Extraer destino_articulo desde texto_nuevo si está disponible
            if current.texto_nuevo:
                extracted_article = extract_article_number_from_texto_nuevo(current.texto_nuevo)
                if extracted_article:
                    current.destino_articulo = extracted_article
        # Agregar al título actual
        get_current_ops().append(current)

    return titulos_ops


def parse_dictamen_pdf(pdf_path: str) -> Dict[str, List[Operation]]:
    """
    Parsea un PDF de dictamen y retorna las operaciones agrupadas por título.
    
    Args:
        pdf_path: Ruta al archivo PDF del dictamen
    
    Returns:
        Diccionario donde las claves son números de título (I, II, etc.)
        y los valores son listas de operaciones
    """
    raw = extract_lines_from_pdf(pdf_path)
    lines = normalize_lines(raw)
    return parse_dictamen(lines)


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Parsea dictámenes y extrae operaciones + texto nuevo desde un PDF.")
    ap.add_argument("pdf", help="Ruta al PDF del dictamen.")
    ap.add_argument("-o", "--output", default="dictamen_parseado", help="Prefijo para los archivos JSON de salida (se generará uno por título).")
    ap.add_argument("--pretty", action="store_true", help="JSON con indentación.")
    args = ap.parse_args()

    titulos_ops = parse_dictamen_pdf(args.pdf)
    
    # Guardar archivo de texto plano normalizado (útil para debugging y ajuste de regex)
    raw = extract_lines_from_pdf(args.pdf)
    lines = normalize_lines(raw)
    text_output = f"{args.output}_normalizado.txt"
    with open(text_output, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines, 1):
            f.write(f"{i:5d}|{line}\n")
    print(f"Archivo de texto normalizado guardado: {text_output}")

    # Generar un archivo JSON por cada título
    total_ops = 0
    for titulo_num, ops in titulos_ops.items():
        payload: List[Dict[str, Any]] = [asdict(op) for op in ops]
        
        # Nombre del archivo basado en el título
        output_file = f"{args.output}_titulo_{titulo_num}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            if args.pretty:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            else:
                json.dump(payload, f, ensure_ascii=False)
        
        with_text = sum(1 for x in payload if x.get("texto_nuevo"))
        print(f"Título {titulo_num}: {len(payload)} operaciones ({with_text} con texto nuevo) -> {output_file}")
        total_ops += len(payload)

    # Resumen general
    print(f"\nTotal de títulos encontrados: {len(titulos_ops)}")
    print(f"Total de operaciones: {total_ops}")


if __name__ == "__main__":
    main()

