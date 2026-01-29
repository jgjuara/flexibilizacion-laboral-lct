#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser de dictámenes legislativos que modifican normas existentes.

Este módulo parsea documentos PDF de dictámenes donde aparecen dos niveles
de "ARTÍCULO":
  (a) Artículo del dictamen: la operación legislativa (ej: "ARTÍCULO 1- Sustitúyese...")
  (b) Artículo de la ley: el texto que se incorpora o modifica (ej: "ARTÍCULO 2°- Ámbito...")

Estrategia de parsing (máquina de estados):
  1. Detecta encabezados "ARTÍCULO N°-" que pueden ser artículos del dictamen.
  2. Clasifica como artículo del dictamen si contiene verbos operativos:
     - Sustitúyese, Incorpórase, Derógase, Modifícase, Créase, etc.
  3. Busca gatillos que indican inicio del texto nuevo:
     - "por el siguiente:", "el siguiente texto:", etc.
  4. Captura el texto nuevo hasta encontrar:
     - Un nuevo artículo del dictamen
     - Un encabezado estructural (TÍTULO, CAPÍTULO, SECCIÓN)
  5. Construye objetos estructurados con el texto completo y metadatos.

Salida:
  Lista de DictamenArticulo, cada uno con:
    - dictamen_articulo: número del artículo del dictamen
    - titulo: título del dictamen (I, II, III, etc.)
    - texto_completo: texto completo del artículo (encabezado + texto nuevo)
    - objetivo_accion: objeto estructurado con metadatos de la operación
      (puede estar vacío si se usa la flag --sin-objetivo-accion)

Requisitos:
  - pdfplumber (recomendado) o PyMuPDF (fitz) como fallback para extraer texto del PDF.
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
# Extracción mejorada de leyes (integrada de extraer_leyes_modificadas.py)
# ----------------------------

# Mapeo de nombres comunes de leyes a sus números
LEY_NOMBRES_A_NUMEROS = {
    "ley de contrato de trabajo": "20744",
    "lct": "20744",
    "ley 20744": "20744",
    "ley n° 20744": "20744",
    "ley n° 20.744": "20744",
    "ley 20.744": "20744",
    "ley de honorarios": "27423",
    "ley n° 27.423": "27423",
    "ley 27.423": "27423",
    "ley n° 27423": "27423",
    "ley 27423": "27423",
    "ley de impuesto a las ganancias": "IMPUESTO_GANANCIAS",  # Marcador especial
    "ley de organización y procedimiento de la justicia nacional de trabajo": "18345",
    "ley complementaria de la ley sobre riesgos del trabajo": "27348",
    "ley sobre riesgos del trabajo": "24557",  # Ley base de riesgos del trabajo
}

# Patrón especial para "Ley de Contrato de Trabajo N° 20.744"
# Este patrón captura el número que viene después del nombre de la ley
PATRON_LEY_CON_NOMBRE = re.compile(
    r"ley\s+de\s+contrato\s+de\s+trabajo\s+n[°º]\s*([0-9\.\-]+)",
    re.IGNORECASE
)

# Patrones de texto que indican que se está hablando de la LCT
PATRONES_LCT = [
    re.compile(r"ley\s+de\s+contrato\s+de\s+trabajo", re.IGNORECASE),
    re.compile(r"art[íi]culo\s+\d+.*de\s+la\s+ley", re.IGNORECASE),
    re.compile(r"sustit[úu]yese.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
    re.compile(r"modif[íi]case.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
    re.compile(r"incorp[óo]rase.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
]

# Patrones para extraer números de ley
PATRONES_LEY_MEJORADOS = [
    re.compile(r"ley\s+n[°º]\s*([0-9\.\-]+)", re.IGNORECASE),
    re.compile(r"ley\s+([0-9\.\-]+)", re.IGNORECASE),
    re.compile(r"ley\s+([0-9]{1,2}\.[0-9]{3,5})", re.IGNORECASE),
    re.compile(r"ley\s+([0-9]{2}\.[0-9]{3,5})", re.IGNORECASE),
    re.compile(r"decreto\s+ley\s+([0-9\.]+)", re.IGNORECASE),
    re.compile(r"decreto[\s-]ley\s+([0-9\.]+)", re.IGNORECASE),
]


def extraer_ley_mejorada(texto: str, contexto_titulo: Optional[str] = None) -> Optional[str]:
    """
    Extrae el número de ley mencionado en un texto usando lógica mejorada.
    Retorna el número de ley normalizado (sin puntos) o None.
    
    Args:
        texto: Texto a analizar
        contexto_titulo: Número de título del dictamen (para inferir leyes por contexto)
    
    Estrategia:
    1. Buscar leyes explícitas mencionadas con número
    2. Priorizar la ley que aparece en contextos clave (después del verbo operativo)
    3. Si hay múltiples leyes, elegir la que está siendo modificada (no las referenciadas)
    4. Como último recurso, inferir por contexto
    """
    if not texto:
        return None
    
    texto_lower = texto.lower()
    
    # Separar leyes explícitas de inferidas
    leyes_explicitas = []  # Lista de tuplas (numero_ley, posicion, contexto)
    leyes_inferidas = set()
    
    # Buscar patrón especial "Ley de Contrato de Trabajo N° 20.744" primero
    for match in PATRON_LEY_CON_NOMBRE.finditer(texto):
        numero = match.group(1).replace(".", "").replace(" ", "").strip()
        if numero and numero.isdigit():
            start = max(0, match.start() - 50)
            end = min(len(texto), match.end() + 50)
            contexto = texto[start:end].lower()
            
            leyes_explicitas.append({
                'numero': numero,
                'posicion': match.start(),
                'contexto': contexto,
                'match_completo': match.group(0),
                'prioridad': 1  # Alta prioridad para este patrón
            })
    
    # Buscar patrones de números de ley con su posición y contexto
    for patron in PATRONES_LEY_MEJORADOS:
        for match in patron.finditer(texto):
            numero = match.group(1).replace(".", "").replace(" ", "").strip()
            if numero and numero.isdigit():
                # Evitar duplicados
                if any(l['numero'] == numero and abs(l['posicion'] - match.start()) < 10 for l in leyes_explicitas):
                    continue
                
                # Extraer contexto alrededor de la mención (50 chars antes y después)
                start = max(0, match.start() - 50)
                end = min(len(texto), match.end() + 50)
                contexto = texto[start:end].lower()
                
                leyes_explicitas.append({
                    'numero': numero,
                    'posicion': match.start(),
                    'contexto': contexto,
                    'match_completo': match.group(0),
                    'prioridad': 2  # Prioridad normal
                })
    
    # Buscar nombres comunes de leyes (explícitas)
    for nombre, numero in LEY_NOMBRES_A_NUMEROS.items():
        if nombre in texto_lower:
            # Encontrar posición de la mención
            pos = texto_lower.find(nombre)
            
            # Evitar duplicados
            if any(l['numero'] == numero and abs(l['posicion'] - pos) < 10 for l in leyes_explicitas):
                continue
            
            start = max(0, pos - 50)
            end = min(len(texto), pos + len(nombre) + 50)
            contexto = texto[start:end].lower()
            
            leyes_explicitas.append({
                'numero': numero,
                'posicion': pos,
                'contexto': contexto,
                'match_completo': nombre,
                'prioridad': 1  # Alta prioridad para nombres conocidos
            })
    
    # Si hay leyes explícitas, aplicar lógica de priorización
    if leyes_explicitas:
        # Ordenar por prioridad primero, luego por posición
        leyes_explicitas.sort(key=lambda x: (x.get('prioridad', 2), x['posicion']))
        
        # Buscar verbos operativos en el texto
        verbo_match = OP_VERB_RE.search(texto)
        verbo_pos = verbo_match.start() if verbo_match else 0
        
        # Prioridad 1: Ley mencionada inmediatamente después del verbo operativo
        # Patrones como "Sustitúyese el artículo X de la Ley N° YYYY"
        # o "Incorpórase como artículo X a la Ley N° YYYY"
        # o "Derógase el artículo X de la Ley N° YYYY"
        
        # Buscar la primera ley después del verbo que esté en contexto de modificación
        for ley in leyes_explicitas:
            if ley['posicion'] > verbo_pos:
                # Verificar que está en contexto de modificación directa
                # (no es una referencia dentro del texto nuevo)
                contexto = ley['contexto']
                
                # Calcular distancia desde el verbo
                distancia = ley['posicion'] - verbo_pos
                
                # Para derogaciones, la ley mencionada inmediatamente después es la objetivo
                if 'deróga' in contexto or 'deroga' in contexto:
                    # Verificar que está cerca del verbo (dentro de 100 chars)
                    if distancia < 100:
                        return ley['numero']
                
                # Para incorporaciones, buscar "a la Ley" o "de la Ley"
                if 'incorpóra' in contexto or 'incorpora' in contexto:
                    if 'a la ley' in contexto or 'de la ley' in contexto:
                        if distancia < 200:
                            return ley['numero']
                
                # Para sustituciones y modificaciones, buscar la ley más cercana al verbo
                # que esté en contexto de "artículo X de la Ley"
                if 'sustit' in contexto or 'modif' in contexto:
                    # Buscar patrón "artículo X de la Ley"
                    if 'de la ley' in contexto and distancia < 200:
                        # Verificar que no es una referencia interna
                        if not any(frase in contexto for frase in [
                            'anexas a la ley',
                            'términos de la ley',
                            'dispuesto en la ley',
                            'establecido en la ley',
                            'previsto en la ley',
                            'conforme a la ley',
                            'según la ley',
                            'en virtud de lo establecido en la ley',
                            'incluyen los entes previstos',
                        ]):
                            return ley['numero']
                
                # Para cualquier verbo, si está muy cerca y en contexto de artículo
                if distancia < 150 and any(palabra in contexto for palabra in ['artículo', 'inciso', 'capítulo']):
                    # Verificar que no es una referencia interna
                    if not any(frase in contexto for frase in [
                        'anexas a la ley',
                        'términos de la ley',
                        'dispuesto en la ley',
                        'establecido en la ley',
                        'previsto en la ley',
                        'conforme a la ley',
                        'según la ley',
                        'en virtud de lo establecido en la ley',
                        'incluyen los entes previstos',
                    ]):
                        return ley['numero']
        
        # Prioridad 2: Primera ley mencionada en el encabezado (antes de "el siguiente:")
        gatillo_match = TRIGGER_RE.search(texto)
        gatillo_pos = gatillo_match.start() if gatillo_match else len(texto)
        
        leyes_antes_gatillo = [l for l in leyes_explicitas if l['posicion'] < gatillo_pos]
        if leyes_antes_gatillo:
            # De las leyes antes del gatillo, buscar la que está en contexto de modificación
            for ley in leyes_antes_gatillo:
                contexto = ley['contexto']
                # Verificar que está asociada al verbo operativo
                if verbo_match and abs(ley['posicion'] - verbo_pos) < 200:
                    # Excluir referencias que claramente no son el objetivo
                    if not any(frase in contexto for frase in [
                        'tablas anexas',
                        'índices de relación contenidos en',
                        'en los términos',
                        'conforme',
                        'según',
                    ]):
                        return ley['numero']
            
            # Si no encontramos una clara, tomar la primera antes del gatillo
            return leyes_antes_gatillo[0]['numero']
        
        # Prioridad 3: Si solo hay una ley explícita, usarla
        numeros_unicos = list(set(l['numero'] for l in leyes_explicitas))
        if len(numeros_unicos) == 1:
            return numeros_unicos[0]
        
        # Prioridad 4: Si hay múltiples leyes, preferir 20744 solo si está en el encabezado
        if '20744' in numeros_unicos:
            for ley in leyes_explicitas:
                if ley['numero'] == '20744' and ley['posicion'] < 300:  # Primeros 300 chars
                    return '20744'
        
        # Prioridad 5: Tomar la primera ley mencionada
        return leyes_explicitas[0]['numero']
    
    # Detectar menciones implícitas de LCT (solo si no hay ley explícita)
    if not leyes_explicitas:
        for patron_lct in PATRONES_LCT:
            if patron_lct.search(texto):
                leyes_inferidas.add("20744")
                break
    
    # Si el título es I y menciona "de la ley" o "esta ley" sin número específico,
    # es muy probable que sea LCT (20744)
    if contexto_titulo == "I" and not leyes_explicitas:
        if re.search(r"(?:de\s+la\s+ley|esta\s+ley)", texto_lower):
            tiene_ley_explicita = any(patron.search(texto) for patron in PATRONES_LEY_MEJORADOS)
            if not tiene_ley_explicita:
                leyes_inferidas.add("20744")
    
    # Si no hay leyes explícitas, usar inferidas
    if leyes_inferidas:
        return list(leyes_inferidas)[0]
    
    return None


# ----------------------------
# Modelo de salida
# ----------------------------

@dataclass
class ObjetivoAccion:
    """Objeto estructurado que describe el objetivo de la acción del artículo del dictamen."""
    tipo: Optional[str] = None  # "nuevo" | "modifica"
    ley_afectada: Optional[str] = None
    accion: Optional[str] = None  # "sustituye" | "incorpora" | "deroga" | "modifica" | "suprime" | "reemplaza" | "crea"
    destino_articulo: Optional[str] = None
    destino_inciso: Optional[str] = None
    destino_articulo_padre: Optional[str] = None
    destino_capitulo: Optional[str] = None
    descripcion: Optional[str] = None
    texto_modificacion: Optional[str] = None  # Texto de la modificación propuesta (texto nuevo)


@dataclass
class DictamenArticulo:
    """Representa un artículo completo del dictamen con toda su información."""
    dictamen_articulo: str
    titulo: str
    texto_completo: str
    objetivo_accion: ObjetivoAccion


# Mantener Operation para compatibilidad temporal
@dataclass
class Operation:
    dictamen_articulo: str
    encabezado: str
    accion: Optional[str] = None
    ley_numero: Optional[str] = None
    destino_articulo: Optional[str] = None
    destino_inciso: Optional[str] = None
    destino_articulo_padre: Optional[str] = None
    destino_capitulo: Optional[str] = None
    texto_nuevo: Optional[str] = None
    texto_nuevo_lineas: Optional[List[str]] = None


# ----------------------------
# Extracción de texto desde PDF
# ----------------------------

def extract_lines_from_pdf(pdf_path: str) -> List[str]:
    """
    Extrae texto del PDF línea por línea, preservando el orden del documento.
    
    Intenta usar pdfplumber primero (más preciso para extracción de texto).
    Si pdfplumber no está disponible o falla, usa PyMuPDF (fitz) como fallback.
    
    Args:
        pdf_path: Ruta al archivo PDF del dictamen.
    
    Returns:
        Lista de strings, cada uno representando una línea de texto del PDF
        en el orden en que aparecen en el documento.
    
    Raises:
        RuntimeError: Si no se puede extraer texto del PDF (ambas librerías fallan).
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
    Normaliza las líneas extraídas del PDF para mejorar el parsing.
    
    Realiza las siguientes transformaciones:
    1. Elimina encabezados/pies de página evidentes (números de página, etc.)
    2. Une palabras partidas por guión al final de línea (ej: "contra-\nto" -> "contrato")
    3. Colapsa espacios múltiples y tabs a un solo espacio
    4. Elimina espacios al final de cada línea
    
    Args:
        raw_lines: Lista de líneas crudas extraídas del PDF.
    
    Returns:
        Lista de líneas normalizadas, listas para el parsing.
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


def is_dictamen_header(lines: List[str], idx: int) -> Tuple[bool, str, int, bool]:
    """
    Determina si lines[idx] es un encabezado de artículo del dictamen.
    
    Un encabezado de artículo del dictamen se identifica por:
    - Coincide con el patrón "ARTÍCULO N°-"
    - Contiene verbos operativos (Sustitúyese, Incorpórase, etc.)
    
    Esta función también consume líneas adicionales del encabezado (hasta 5 líneas)
    hasta encontrar el gatillo que indica el inicio del texto nuevo, o hasta
    encontrar un delimitador (nuevo artículo, encabezado estructural).
    
    Args:
        lines: Lista de líneas de texto normalizadas del dictamen.
        idx: Índice de la línea a verificar.
    
    Returns:
        Tupla (es_dictamen, encabezado_completo, idx_siguiente, gatillo_encontrado):
        - es_dictamen: True si es un encabezado de artículo del dictamen.
        - encabezado_completo: Texto completo del encabezado (puede incluir múltiples líneas).
        - idx_siguiente: Índice de la siguiente línea a procesar (después de consumir el encabezado).
        - gatillo_encontrado: True si se encontró el gatillo "por el siguiente:" en el encabezado.
                              Esto es importante porque indica que la captura de texto nuevo
                              debe iniciarse inmediatamente.
    
    Nota:
        El flag gatillo_encontrado es crítico para evitar que encabezados estructurales
        (como "CAPÍTULO VII") se incluyan en el texto del artículo anterior.
    """
    m = HEADER_RE.match(lines[idx])
    if not m:
        return (False, "", idx + 1, False)

    art_num = m.group(1).strip()
    tail = (m.group(2) or "").strip()

    # Si la primera línea ya tiene verbo operativo
    if looks_like_dictamen_header(tail):
        # Capturar líneas adicionales hasta el gatillo o nuevo artículo
        header_parts = [f"ARTÍCULO {art_num}- {tail}"]
        j = idx + 1
        gatillo_encontrado = False
        
        # Capturar hasta 5 líneas más o hasta encontrar gatillo/nuevo artículo
        max_lines = 5
        lines_captured = 0
        while j < len(lines) and lines_captured < max_lines:
            line = lines[j].strip()
            if not line:
                j += 1
                continue
            
            # Si encontramos gatillo, incluir esta línea y terminar
            if TRIGGER_RE.search(line):
                header_parts.append(line)
                j += 1
                gatillo_encontrado = True
                break
            
            # Si encontramos nuevo artículo, terminar sin incluir
            if HEADER_RE.match(line):
                break
            
            # Si encontramos encabezado estructural, terminar
            if STRUCT_RE.match(line):
                break
            
            # Incluir la línea
            header_parts.append(line)
            j += 1
            lines_captured += 1
        
        combined = " ".join(header_parts)
        return (True, combined, j, gatillo_encontrado)

    # Caso: "ARTÍCULO N°-" y el verbo viene en la línea siguiente
    j, nxt = find_next_nonempty(lines, idx + 1)
    if nxt and looks_like_dictamen_header(nxt):
        # Capturar líneas adicionales
        header_parts = [f"ARTÍCULO {art_num}- {nxt.strip()}"]
        j += 1
        gatillo_encontrado = False
        
        max_lines = 5
        lines_captured = 0
        while j < len(lines) and lines_captured < max_lines:
            line = lines[j].strip()
            if not line:
                j += 1
                continue
            
            if TRIGGER_RE.search(line):
                header_parts.append(line)
                j += 1
                gatillo_encontrado = True
                break
            
            if HEADER_RE.match(line) or STRUCT_RE.match(line):
                break
            
            header_parts.append(line)
            j += 1
            lines_captured += 1
        
        combined = " ".join(header_parts)
        return (True, combined, j, gatillo_encontrado)

    return (False, "", idx + 1, False)


def parse_action_and_target(header_text: str, contexto_titulo: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Extrae metadatos básicos de la operación legislativa desde el encabezado.
    
    Analiza el texto del encabezado del artículo del dictamen para extraer:
    - El verbo operativo (sustitúyese, incorpórase, derógase, etc.)
    - El número de ley afectada (usando lógica mejorada que considera contexto)
    - El destino de la operación (artículo, inciso, capítulo, etc.)
    
    La extracción de la ley usa heurísticas mejoradas que consideran:
    - Posición relativa al verbo operativo
    - Contexto del título del dictamen
    - Patrones comunes de referencia a leyes
    
    Args:
        header_text: Texto completo del encabezado del artículo del dictamen.
        contexto_titulo: Número de título del dictamen (I, II, etc.) para inferir leyes.
    
    Returns:
        Diccionario con los campos extraídos:
        - accion: Verbo operativo en minúsculas (sustitúyese, incorpórase, etc.)
        - ley_numero: Número de ley afectada (sin puntos, ej: "20744")
        - destino_articulo: Número de artículo destino
        - destino_inciso: Inciso destino (si aplica)
        - destino_articulo_padre: Artículo padre del inciso (si aplica)
        - destino_capitulo: Capítulo destino (si aplica, para derogaciones)
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

    # Usar lógica mejorada para extraer ley
    out["ley_numero"] = extraer_ley_mejorada(header_text, contexto_titulo)

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
    if out["accion"] in ("sustitúyese", "sustituyese", "derógase", "derogase", "modifícase", "modificase", "suprímese", "suprimese", "reemplázase", "reemplazase"):
        mart_after_verb = TARGET_ART_AFTER_VERB_RE.search(header_text)
        if mart_after_verb:
            out["destino_articulo"] = mart_after_verb.group(1).strip()
            return out

    # Fallback: buscar cualquier "artículo X"
    mart = TARGET_ART_RE.search(header_text)
    if mart:
        out["destino_articulo"] = mart.group(1).strip()

    return out


def crear_objetivo_accion_vacio() -> ObjetivoAccion:
    """
    Crea un ObjetivoAccion vacío con todos los campos en None.
    
    Útil cuando se necesita generar el JSON con solo el esquema declarado,
    sin completar los campos con datos parseados. Esto permite que el
    procesamiento de objetivo_accion se haga en una etapa posterior.
    
    Returns:
        ObjetivoAccion con todos los campos (tipo, ley_afectada, accion, etc.) en None.
    """
    return ObjetivoAccion(
        tipo=None,
        ley_afectada=None,
        accion=None,
        destino_articulo=None,
        destino_inciso=None,
        destino_articulo_padre=None,
        destino_capitulo=None,
        descripcion=None,
        texto_modificacion=None,
    )


def construir_objetivo_accion(
    encabezado: str,
    texto_nuevo: Optional[str],
    accion: Optional[str],
    ley_numero: Optional[str],
    destino_articulo: Optional[str],
    destino_inciso: Optional[str],
    destino_articulo_padre: Optional[str],
    destino_capitulo: Optional[str],
    contexto_titulo: Optional[str] = None,
) -> ObjetivoAccion:
    """
    Construye un objeto ObjetivoAccion completo a partir de los datos extraídos.
    
    Esta función procesa los metadatos extraídos del encabezado y texto del artículo
    para construir un objeto estructurado que describe el objetivo de la acción
    legislativa.
    
    Procesos realizados:
    1. Determina el tipo: "nuevo" (crea texto nuevo) o "modifica" (modifica existente)
    2. Mejora la extracción de la ley afectada si no se encontró en el encabezado
    3. Normaliza la acción (sustitúyese -> sustituye, etc.)
    4. Extrae el número de artículo destino desde el texto nuevo si no está en el encabezado
    5. Genera una descripción textual del objetivo
    6. Limpia y formatea el texto de modificación
    
    Args:
        encabezado: Texto completo del encabezado del artículo del dictamen.
        texto_nuevo: Texto nuevo que se incorpora o modifica (después del gatillo).
        accion: Verbo operativo extraído (sustitúyese, incorpórase, etc.).
        ley_numero: Número de ley afectada extraído del encabezado.
        destino_articulo: Número de artículo destino extraído del encabezado.
        destino_inciso: Inciso destino (si aplica).
        destino_articulo_padre: Artículo padre del inciso (si aplica).
        destino_capitulo: Capítulo destino (si aplica, para derogaciones).
        contexto_titulo: Número de título del dictamen (para inferir leyes por contexto).
    
    Returns:
        ObjetivoAccion con todos los campos completados según los datos disponibles.
    """
    # Determinar tipo: "nuevo" o "modifica"
    tipo = "modifica"
    if accion in ("créase", "crease") or (accion == "incorpórase" and not destino_articulo):
        tipo = "nuevo"
    
    # Mejorar extracción de ley si no se encontró en el encabezado
    ley_afectada = ley_numero
    if not ley_afectada:
        # Buscar en encabezado y texto nuevo
        texto_completo = encabezado
        if texto_nuevo:
            texto_completo += "\n" + texto_nuevo
        ley_afectada = extraer_ley_mejorada(texto_completo, contexto_titulo)
    
    # Normalizar acción
    accion_normalizada = None
    if accion:
        accion_map = {
            "sustitúyese": "sustituye",
            "sustituyese": "sustituye",
            "incorpórase": "incorpora",
            "incorporase": "incorpora",
            "derógase": "deroga",
            "derogase": "deroga",
            "modifícase": "modifica",
            "modificase": "modifica",
            "suprímese": "suprime",
            "suprimese": "suprime",
            "reemplázase": "reemplaza",
            "reemplazase": "reemplaza",
            "créase": "crea",
            "crease": "crea",
        }
        accion_normalizada = accion_map.get(accion.lower())
    
    # Extraer destino_articulo desde texto_nuevo si no está en encabezado
    destino_art_final = destino_articulo
    if not destino_art_final and texto_nuevo:
        destino_art_final = extract_article_number_from_texto_nuevo(texto_nuevo)
    
    # Generar descripción
    descripcion = _generar_descripcion_objetivo(
        tipo, ley_afectada, accion_normalizada, destino_art_final,
        destino_inciso, destino_articulo_padre, destino_capitulo
    )
    
    # Extraer texto de modificación (texto nuevo limpio)
    texto_modificacion = None
    if texto_nuevo:
        # El texto_nuevo ya está limpio, solo asegurarse de que esté bien formateado
        texto_modificacion = texto_nuevo.strip()
        # Si está vacío después de strip, dejarlo como None
        if not texto_modificacion:
            texto_modificacion = None
    
    return ObjetivoAccion(
        tipo=tipo,
        ley_afectada=ley_afectada,
        accion=accion_normalizada,
        destino_articulo=destino_art_final,
        destino_inciso=destino_inciso,
        destino_articulo_padre=destino_articulo_padre,
        destino_capitulo=destino_capitulo,
        descripcion=descripcion,
        texto_modificacion=texto_modificacion,
    )


def _generar_descripcion_objetivo(
    tipo: str,
    ley_afectada: Optional[str],
    accion: Optional[str],
    destino_articulo: Optional[str],
    destino_inciso: Optional[str],
    destino_articulo_padre: Optional[str],
    destino_capitulo: Optional[str],
) -> str:
    """Genera una descripción textual del objetivo de la acción."""
    partes = []
    
    if accion:
        partes.append(accion.capitalize())
    
    if tipo == "nuevo":
        if destino_articulo:
            partes.append(f"como artículo {destino_articulo}")
        if ley_afectada:
            partes.append(f"en la Ley {ley_afectada}")
        else:
            partes.append("nuevo texto legal")
    else:  # modifica
        if destino_capitulo:
            partes.append(f"el capítulo {destino_capitulo}")
        elif destino_inciso and destino_articulo_padre:
            partes.append(f"el inciso {destino_inciso} del artículo {destino_articulo_padre}")
        elif destino_articulo:
            partes.append(f"el artículo {destino_articulo}")
        
        if ley_afectada:
            partes.append(f"de la Ley {ley_afectada}")
    
    if not partes:
        return "Acción no especificada"
    
    return " ".join(partes)


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

def parse_dictamen(lines: List[str], fill_objetivo_accion: bool = True) -> List[DictamenArticulo]:
    """
    Parsea el dictamen completo y retorna una lista de artículos estructurados.
    
    Esta es la función principal del parser. Implementa una máquina de estados que:
    1. Detecta títulos del dictamen (TÍTULO I, II, etc.)
    2. Identifica artículos del dictamen (ARTÍCULO N°- con verbos operativos)
    3. Captura el texto completo de cada artículo hasta encontrar delimitadores
    4. Construye objetos DictamenArticulo con toda la información
    
    Estados de la máquina:
    - Sin artículo: buscando inicio de artículo del dictamen
    - Capturando encabezado: capturando líneas del encabezado antes del gatillo
    - Capturando texto nuevo: capturando el texto que se incorpora/modifica
    
    Delimitadores que finalizan un artículo:
    - Nuevo artículo del dictamen (ARTÍCULO N°-)
    - Encabezados estructurales (TÍTULO, CAPÍTULO, SECCIÓN)
    - Nuevo título del dictamen
    
    Args:
        lines: Lista de líneas de texto normalizadas del dictamen.
        fill_objetivo_accion: Si True, completa objetivo_accion con datos parseados
                             (ley afectada, acción, destino, etc.).
                             Si False, deja objetivo_accion vacío con todos los campos en None.
    
    Returns:
        Lista de DictamenArticulo, cada uno representando un artículo completo del dictamen.
    """
    articulos: List[DictamenArticulo] = []
    current_titulo: Optional[str] = None
    i = 0

    # Estado para capturar texto completo
    current_encabezado: Optional[str] = None
    current_encabezado_completo: List[str] = []
    current_texto_intermedio: List[str] = []
    current_texto_nuevo: List[str] = []
    current_meta: Optional[Dict[str, Optional[str]]] = None
    current_dictamen_art: Optional[str] = None
    capturing_new_text = False
    capturing_header = False

    def finalizar_articulo_actual() -> None:
        """Finaliza el artículo actual y lo agrega a la lista."""
        nonlocal current_encabezado, current_encabezado_completo, current_texto_intermedio
        nonlocal current_texto_nuevo, current_meta, current_dictamen_art, capturing_new_text, capturing_header
        
        if not current_dictamen_art or not current_meta:
            return
        
        # Construir texto completo
        texto_completo_parts = []
        
        # Encabezado completo
        if current_encabezado_completo:
            texto_completo_parts.append("\n".join(current_encabezado_completo))
        
        # Texto intermedio
        if current_texto_intermedio:
            texto_completo_parts.append("\n".join(current_texto_intermedio))
        
        # Texto nuevo
        if current_texto_nuevo:
            texto_completo_parts.append("\n".join(current_texto_nuevo))
        
        texto_completo = "\n".join(texto_completo_parts).strip()
        
        # Construir objetivo de acción
        if fill_objetivo_accion:
            texto_nuevo_str = "\n".join(current_texto_nuevo).strip() if current_texto_nuevo else None
            objetivo = construir_objetivo_accion(
                encabezado=current_encabezado or "",
                texto_nuevo=texto_nuevo_str,
                accion=current_meta["accion"],
                ley_numero=current_meta["ley_numero"],
                destino_articulo=current_meta["destino_articulo"],
                destino_inciso=current_meta["destino_inciso"],
                destino_articulo_padre=current_meta["destino_articulo_padre"],
                destino_capitulo=current_meta["destino_capitulo"],
                contexto_titulo=current_titulo or "SIN_TITULO",
            )
        else:
            objetivo = crear_objetivo_accion_vacio()
        
        # Crear artículo
        titulo_final = current_titulo or "SIN_TITULO"
        articulo = DictamenArticulo(
            dictamen_articulo=current_dictamen_art,
            titulo=titulo_final,
            texto_completo=texto_completo,
            objetivo_accion=objetivo,
        )
        articulos.append(articulo)
        
        # Resetear estado
        current_encabezado = None
        current_encabezado_completo = []
        current_texto_intermedio = []
        current_texto_nuevo = []
        current_meta = None
        current_dictamen_art = None
        capturing_new_text = False
        capturing_header = False

    while i < len(lines):
        line = lines[i]

        # Detectar inicio de nuevo título
        titulo_match = TITULO_RE.match(line)
        if not titulo_match:
            titulo_match = TITULO_RE_ANYWHERE.search(line)
        
        if titulo_match:
            # Finalizar artículo actual si existe
            if current_dictamen_art:
                finalizar_articulo_actual()
            
            # Iniciar nuevo título
            current_titulo = titulo_match.group(1).strip()
            i += 1
            continue

        # Delimitadores fuertes: encabezados estructurales (CAPÍTULO, SECCIÓN, etc.)
        # Solo finalizamos si estamos capturando texto nuevo (no si estamos en encabezado)
        # y no es un nuevo título del dictamen
        if STRUCT_RE.match(line) and current_dictamen_art and capturing_new_text:
            if not TITULO_RE.match(line):
                # Finalizar artículo actual antes del encabezado estructural
                finalizar_articulo_actual()
            i += 1
            continue

        # ¿Es un encabezado de artículo?
        if HEADER_RE.match(line):
            is_dic, full_header, next_i, gatillo_en_header = is_dictamen_header(lines, i)

            if is_dic:
                # Finalizar artículo anterior si existe
                if current_dictamen_art:
                    finalizar_articulo_actual()

                # Iniciar nuevo artículo
                m = HEADER_RE.match(line)
                assert m is not None
                current_dictamen_art = m.group(1).strip()
                current_encabezado = full_header.strip()
                current_encabezado_completo = [full_header.strip()]
                
                # Extraer metadata (acción, ley, destino, etc.)
                current_meta = parse_action_and_target(full_header, current_titulo)
                
                # Si el gatillo fue encontrado en el encabezado (por is_dictamen_header),
                # activar inmediatamente la captura de texto nuevo. Esto evita que
                # encabezados estructurales (como "CAPÍTULO VII") se incluyan en el
                # texto del artículo anterior.
                if gatillo_en_header:
                    capturing_header = False
                    capturing_new_text = True
                else:
                    capturing_header = True
                    capturing_new_text = False
                current_texto_intermedio = []
                current_texto_nuevo = []
                i = next_i
                continue

            # Si NO es dictamen header: puede ser parte del texto nuevo o intermedio
            if current_dictamen_art:
                if capturing_new_text:
                    if line.strip():
                        current_texto_nuevo.append(line.strip())
                elif capturing_header:
                    # Texto intermedio entre encabezado y gatillo
                    if line.strip():
                        current_texto_intermedio.append(line.strip())
                i += 1
                continue

        # Si hay artículo en curso, buscar gatillo para iniciar captura de texto nuevo
        if current_dictamen_art and not capturing_new_text:
            mt = TRIGGER_RE.search(line)
            if mt:
                capturing_new_text = True
                capturing_header = False
                
                # Agregar parte antes del gatillo al intermedio si existe
                before = line[:mt.start()].strip()
                if before:
                    current_texto_intermedio.append(before)
                
                # Agregar parte después del gatillo al texto nuevo
                after = line[mt.end():].strip()
                if after:
                    current_texto_nuevo.append(after)
                i += 1
                continue
            
            # Para incorporaciones, si no hay gatillo, buscar inicio automático
            if current_meta and (current_meta["accion"] == "incorpórase" or current_meta["accion"] == "incorporase"):
                if HEADER_RE.match(line.strip()):
                    capturing_new_text = True
                    capturing_header = False
                    if line.strip():
                        current_texto_nuevo.append(line.strip())
                    i += 1
                    continue
                elif line.strip() and i < len(lines) - 1:
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if next_line and not STRUCT_RE.match(next_line) and not TITULO_RE.match(next_line):
                        if not re.match(r"^\s*\d+\s*$", line.strip()) and not HEADER_RE.match(line.strip()):
                            capturing_new_text = True
                            capturing_header = False
                            current_texto_nuevo.append(line.strip())
                            i += 1
                            continue

        # Capturar texto según el estado
        if current_dictamen_art:
            if capturing_new_text:
                s = line.strip()
                if s:
                    current_texto_nuevo.append(s)
                elif current_texto_nuevo and current_texto_nuevo[-1] != "":
                    current_texto_nuevo.append("")
            elif capturing_header:
                # Continuar capturando encabezado si está en múltiples líneas
                s = line.strip()
                if s:
                    current_encabezado_completo.append(s)
                    # Si la línea siguiente no parece ser parte del encabezado, terminar
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if not OP_VERB_RE.search(next_line) and not TRIGGER_RE.search(next_line):
                            capturing_header = False
            else:
                # Texto intermedio
                s = line.strip()
                if s:
                    current_texto_intermedio.append(s)

        i += 1

    # Cierre final
    if current_dictamen_art:
        finalizar_articulo_actual()

    return articulos


def parse_dictamen_pdf(pdf_path: str, fill_objetivo_accion: bool = True) -> List[DictamenArticulo]:
    """
    Parsea un PDF de dictamen y retorna una lista de artículos del dictamen.
    
    Args:
        pdf_path: Ruta al archivo PDF del dictamen
        fill_objetivo_accion: Si True, completa objetivo_accion con datos parseados.
                             Si False, deja objetivo_accion vacío (solo esquema).
    
    Returns:
        Lista de artículos del dictamen con texto completo y objetivo de acción
    """
    raw = extract_lines_from_pdf(pdf_path)
    lines = normalize_lines(raw)
    return parse_dictamen(lines, fill_objetivo_accion=fill_objetivo_accion)


def parse_dictamen_pdf_legacy(pdf_path: str, fill_objetivo_accion: bool = True) -> Dict[str, List[Operation]]:
    """
    Versión legacy que retorna operaciones agrupadas por título.
    Mantenida para compatibilidad.
    """
    articulos = parse_dictamen_pdf(pdf_path, fill_objetivo_accion=fill_objetivo_accion)
    titulos_ops: Dict[str, List[Operation]] = {}
    
    for articulo in articulos:
        if articulo.titulo not in titulos_ops:
            titulos_ops[articulo.titulo] = []
        
        # Convertir a Operation para compatibilidad
        op = Operation(
            dictamen_articulo=articulo.dictamen_articulo,
            encabezado=articulo.texto_completo.split("\n")[0] if articulo.texto_completo else "",
            accion=articulo.objetivo_accion.accion,
            ley_numero=articulo.objetivo_accion.ley_afectada,
            destino_articulo=articulo.objetivo_accion.destino_articulo,
            destino_inciso=articulo.objetivo_accion.destino_inciso,
            destino_articulo_padre=articulo.objetivo_accion.destino_articulo_padre,
            destino_capitulo=articulo.objetivo_accion.destino_capitulo,
            texto_nuevo=articulo.texto_completo,  # Incluir todo como texto nuevo para compatibilidad
            texto_nuevo_lineas=articulo.texto_completo.split("\n") if articulo.texto_completo else None,
        )
        titulos_ops[articulo.titulo].append(op)
    
    return titulos_ops


# ----------------------------
# CLI
# ----------------------------

def _dictamen_articulo_to_dict(articulo: DictamenArticulo) -> Dict[str, Any]:
    """Convierte DictamenArticulo a diccionario para JSON."""
    return {
        "dictamen_articulo": articulo.dictamen_articulo,
        "titulo": articulo.titulo,
        "texto_completo": articulo.texto_completo,
        "objetivo_accion": {
            "tipo": articulo.objetivo_accion.tipo,
            "ley_afectada": articulo.objetivo_accion.ley_afectada,
            "accion": articulo.objetivo_accion.accion,
            "destino_articulo": articulo.objetivo_accion.destino_articulo,
            "destino_inciso": articulo.objetivo_accion.destino_inciso,
            "destino_articulo_padre": articulo.objetivo_accion.destino_articulo_padre,
            "destino_capitulo": articulo.objetivo_accion.destino_capitulo,
            "descripcion": articulo.objetivo_accion.descripcion,
            "texto_modificacion": articulo.objetivo_accion.texto_modificacion,
        },
    }


def main() -> None:
    """
    Punto de entrada principal del parser desde línea de comandos.
    
    Ejemplos de uso:
        # Parsear con objetivo_accion completo (por defecto)
        python parser.py dictamen.pdf -o salida --pretty
        
        # Parsear con objetivo_accion vacío (solo esquema)
        python parser.py dictamen.pdf -o salida --pretty --sin-objetivo-accion
        
        # Generar archivos separados por título (formato legacy)
        python parser.py dictamen.pdf --por-titulo
    """
    ap = argparse.ArgumentParser(
        description="Parsea dictámenes legislativos y extrae artículos con texto completo "
                   "y objetivo de acción desde un PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s dictamen.pdf -o salida --pretty
  %(prog)s dictamen.pdf --sin-objetivo-accion
  %(prog)s dictamen.pdf --por-titulo
        """
    )
    ap.add_argument("pdf", help="Ruta al archivo PDF del dictamen.")
    ap.add_argument(
        "-o", "--output",
        default="dictamen_parseado",
        help="Nombre del archivo JSON de salida (sin extensión). Por defecto: dictamen_parseado"
    )
    ap.add_argument(
        "--pretty",
        action="store_true",
        help="Generar JSON con indentación (más legible pero ocupa más espacio)."
    )
    ap.add_argument(
        "--por-titulo",
        action="store_true",
        help="Generar archivos separados por título (formato legacy). "
             "Cada título se guarda en un archivo distinto: output_titulo_I.json, etc."
    )
    ap.add_argument(
        "--sin-objetivo-accion",
        action="store_true",
        help="Generar objetivo_accion vacío (solo esquema con campos en None, sin datos parseados). "
             "Útil cuando el procesamiento de objetivo_accion se hará en una etapa posterior."
    )
    args = ap.parse_args()

    fill_objetivo_accion = not args.sin_objetivo_accion
    articulos = parse_dictamen_pdf(args.pdf, fill_objetivo_accion=fill_objetivo_accion)
    
    # Guardar archivo de texto plano normalizado (útil para debugging)
    raw = extract_lines_from_pdf(args.pdf)
    lines = normalize_lines(raw)
    text_output = f"{args.output}_normalizado.txt"
    with open(text_output, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines, 1):
            f.write(f"{i:5d}|{line}\n")
    print(f"Archivo de texto normalizado guardado: {text_output}")

    if args.por_titulo:
        # Formato legacy: archivos por título
        titulos_ops = parse_dictamen_pdf_legacy(args.pdf, fill_objetivo_accion=fill_objetivo_accion)
        total_ops = 0
        for titulo_num, ops in titulos_ops.items():
            payload: List[Dict[str, Any]] = [asdict(op) for op in ops]
            output_file = f"{args.output}_titulo_{titulo_num}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                if args.pretty:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(payload, f, ensure_ascii=False)
            with_text = sum(1 for x in payload if x.get("texto_nuevo"))
            print(f"Título {titulo_num}: {len(payload)} operaciones ({with_text} con texto nuevo) -> {output_file}")
            total_ops += len(payload)
        print(f"\nTotal de títulos encontrados: {len(titulos_ops)}")
        print(f"Total de operaciones: {total_ops}")
    else:
        # Formato nuevo: un único archivo con todos los artículos
        output_file = f"{args.output}.json"
        payload: List[Dict[str, Any]] = [_dictamen_articulo_to_dict(art) for art in articulos]
        
        with open(output_file, "w", encoding="utf-8") as f:
            if args.pretty:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            else:
                json.dump(payload, f, ensure_ascii=False)
        
        print(f"\nTotal de artículos del dictamen: {len(articulos)}")
        print(f"Archivo JSON generado: {output_file}")
        
        # Estadísticas por título
        titulos_count: Dict[str, int] = {}
        for art in articulos:
            titulos_count[art.titulo] = titulos_count.get(art.titulo, 0) + 1
        
        print(f"\nArtículos por título:")
        for titulo in sorted(titulos_count.keys()):
            print(f"  Título {titulo}: {titulos_count[titulo]} artículos")


if __name__ == "__main__":
    main()

