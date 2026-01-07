#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parseador de "dictámenes" que modifican normas (ej. LCT) donde aparecen
dos niveles de "ARTÍCULO": (a) artículo del dictamen (operación) y
(b) artículo/inciso del texto que se incorpora a la ley.

Estrategia (parser por estados):
- Detecta encabezados "ARTÍCULO N°-" (posible artículo del dictamen).
- Clasifica como "dictamen" si el encabezado (o la línea siguiente) contiene verbos operativos:
  Sustitúyese / Incorpórase / Derógase / Modifícase / etc.
- Si encuentra gatillos "por el siguiente:" / "el siguiente texto:" empieza a capturar el texto nuevo
  hasta el próximo artículo del dictamen o un encabezado estructural (TÍTULO/CAPÍTULO/SECCIÓN).

Salida: JSON con una lista de operaciones (artículos del dictamen) y su texto nuevo, si aplica.

Uso:
  python parse_dictamen.py "/ruta/al/Dictamen.pdf" -o salida.json

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

# Extracción simple de destino
TARGET_ART_RE = re.compile(r"art[íi]culo\s+([0-9]+(?:\s*(?:bis|ter|quater))?)\s*[°º]?", re.IGNORECASE)
TARGET_INCISO_RE = re.compile(r"inciso\s+([a-z])\)\s+del\s+art[íi]culo\s+([0-9]+)\s*[°º]?", re.IGNORECASE)

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
      - destino_articulo, destino_inciso, destino_articulo_padre
    """
    out: Dict[str, Optional[str]] = {
        "accion": None,
        "ley_numero": None,
        "destino_articulo": None,
        "destino_inciso": None,
        "destino_articulo_padre": None,
    }

    mv = OP_VERB_RE.search(header_text)
    if mv:
        out["accion"] = mv.group(1).lower()

    mlaw = LAW_NUM_RE.search(header_text)
    if mlaw:
        out["ley_numero"] = mlaw.group(1)

    minc = TARGET_INCISO_RE.search(header_text)
    if minc:
        out["destino_inciso"] = f"{minc.group(1)})"
        out["destino_articulo_padre"] = minc.group(2)
        return out

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
    pattern = r"ART[ÍI]CULO\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?-"
    match = re.search(pattern, texto_nuevo, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return None


# ----------------------------
# Parser principal
# ----------------------------

def parse_dictamen(lines: List[str]) -> List[Operation]:
    ops: List[Operation] = []
    i = 0

    current: Optional[Operation] = None
    capturing_new_text = False
    new_text_lines: List[str] = []

    while i < len(lines):
        line = lines[i]

        # Delimitadores fuertes: encabezados estructurales
        if STRUCT_RE.match(line) and current and capturing_new_text:
            # cerrar captura
            current.texto_nuevo_lineas = new_text_lines[:] if new_text_lines else None
            current.texto_nuevo = "\n".join(new_text_lines).strip() if new_text_lines else None
            # Extraer destino_articulo desde texto_nuevo si está disponible
            if current.texto_nuevo:
                extracted_article = extract_article_number_from_texto_nuevo(current.texto_nuevo)
                if extracted_article:
                    current.destino_articulo = extracted_article
            ops.append(current)
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
                    ops.append(current)

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
        ops.append(current)

    return ops


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Parsea dictámenes y extrae operaciones + texto nuevo desde un PDF.")
    ap.add_argument("pdf", help="Ruta al PDF del dictamen.")
    ap.add_argument("-o", "--output", default="dictamen_parseado.json", help="Ruta del JSON de salida.")
    ap.add_argument("--pretty", action="store_true", help="JSON con indentación.")
    args = ap.parse_args()

    raw = extract_lines_from_pdf(args.pdf)
    lines = normalize_lines(raw)
    ops = parse_dictamen(lines)

    payload: List[Dict[str, Any]] = [asdict(op) for op in ops]

    with open(args.output, "w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        else:
            json.dump(payload, f, ensure_ascii=False)

    # Resumen mínimo por stdout
    print(f"Operaciones encontradas: {len(payload)}")
    with_text = sum(1 for x in payload if x.get("texto_nuevo"))
    print(f"Con texto nuevo capturado: {with_text}")
    print(f"Salida: {args.output}")


if __name__ == "__main__":
    main()

