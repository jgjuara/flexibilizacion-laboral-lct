#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lógica de matcheo entre dictámenes (JSON parseado) y leyes (JSON de SAIJ).

Este módulo contiene las funciones para:
- Identificar qué artículos de la ley son afectados por el dictamen
- Encontrar el cambio correspondiente para cada artículo
- Detectar artículos incorporados
- Detectar artículos derogados (individuales o por capítulo)
"""

import re
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass


@dataclass
class MatchResult:
    """Resultado del procesamiento de un dictamen contra una ley."""
    modified_articles: Set[str]
    derogated_articles: Set[str]
    derogated_chapters: Dict[str, Set[str]]
    incorporated_articles: List[Dict[str, Any]]


def extract_article_number_from_header(encabezado: str) -> Optional[str]:
    """
    Extrae el número de artículo desde el encabezado de una operación.
    
    Args:
        encabezado: Texto del encabezado de la operación
    
    Returns:
        Número de artículo o None si no se encuentra
    """
    if not encabezado:
        return None
    
    # Para incorporaciones, buscar "como artículo X" o "artículo X" después de incorpórase
    incorporacion_match = re.search(
        r"incorp[óo]rase\s+como\s+art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)",
        encabezado,
        re.IGNORECASE
    )
    if incorporacion_match:
        return incorporacion_match.group(1).strip()
    
    # Fallback: buscar cualquier "artículo X" con sufijos
    match = re.search(
        r"art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)",
        encabezado,
        re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    
    return None


def get_destino_articulo(cambio: Dict[str, Any]) -> Optional[str]:
    """
    Obtiene el número de artículo destino de una operación.
    
    Prioridad:
    1. destino_articulo explícito
    2. Extraer desde texto_nuevo (más confiable)
    3. Extraer desde encabezado
    
    Args:
        cambio: Diccionario con la operación del dictamen
    
    Returns:
        Número de artículo destino o None
    """
    # Prioridad 1: destino_articulo explícito
    if cambio.get("destino_articulo"):
        return str(cambio["destino_articulo"])
    
    # Prioridad 2: extraer desde texto_nuevo (más confiable)
    if cambio.get("texto_nuevo"):
        match = re.search(
            r"ART[ÍI]CULO\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?-",
            cambio["texto_nuevo"],
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
    
    # Prioridad 3: extraer desde encabezado
    from_header = extract_article_number_from_header(cambio.get("encabezado", ""))
    return from_header if from_header else None


def find_articles_in_chapter(ley_data: Dict[str, Any], capitulo_numero: str) -> List[str]:
    """
    Encuentra todos los artículos en un capítulo específico.
    
    Args:
        ley_data: Estructura JSON de la ley
        capitulo_numero: Número del capítulo (ej: "VIII")
    
    Returns:
        Lista de números de artículos en el capítulo
    """
    articles = []
    titulos = ley_data.get("ley", {}).get("titulos", [])
    
    for titulo in titulos:
        if titulo.get("capitulos"):
            for capitulo in titulo["capitulos"]:
                cap_num = str(capitulo.get("numero", "")).upper()
                target_cap_num = str(capitulo_numero).upper()
                
                if cap_num == target_cap_num and capitulo.get("articulos"):
                    for i, articulo in enumerate(capitulo["articulos"]):
                        # Si el artículo no tiene número o es "S/N", usar un identificador basado en índice
                        numero = str(articulo.get("numero", "")).strip()
                        if numero == "" or numero.upper() == "S/N" or numero == "null":
                            # Crear identificador único: "CAP_VIII_ART_1", "CAP_VIII_ART_2", etc.
                            articles.append(f"CAP_{capitulo_numero}_ART_{i + 1}")
                        else:
                            articles.append(numero)
    
    return articles


def process_dictamen_data(
    dictamen_data: List[Dict[str, Any]],
    ley_data: Dict[str, Any]
) -> MatchResult:
    """
    Procesa los datos del dictamen y determina qué artículos de la ley son afectados.
    
    Args:
        dictamen_data: Lista de operaciones del dictamen
        ley_data: Estructura JSON de la ley
    
    Returns:
        MatchResult con los artículos modificados, derogados, etc.
    """
    modified_articles: Set[str] = set()
    derogated_articles: Set[str] = set()
    derogated_chapters: Dict[str, Set[str]] = {}
    
    for cambio in dictamen_data:
        # Detectar derogaciones de capítulos completos
        if cambio.get("destino_capitulo"):
            capitulo_numero = cambio["destino_capitulo"]
            articles_in_chapter = find_articles_in_chapter(ley_data, capitulo_numero)
            derogated_chapters[capitulo_numero] = set(articles_in_chapter)
            # Marcar todos los artículos del capítulo como modificados
            for art_num in articles_in_chapter:
                modified_articles.add(art_num)
                derogated_articles.add(art_num)
            
            # Si no se encontraron artículos (capítulo no existe o tiene artículos sin número),
            # crear artículos sintéticos para mostrar la derogación
            if len(articles_in_chapter) == 0:
                # Para el Capítulo VIII de Formación Profesional, crear artículos sintéticos
                # basados en la información proporcionada (7 artículos sin número)
                if capitulo_numero.upper() == "VIII":
                    # Crear identificadores para los 7 artículos sin número del Capítulo VIII
                    synthetic_articles = [f"CAP_VIII_ART_{i}" for i in range(1, 8)]
                    for art_id in synthetic_articles:
                        modified_articles.add(art_id)
                        derogated_articles.add(art_id)
                    derogated_chapters[capitulo_numero] = set(synthetic_articles)
        else:
            # Otras modificaciones (incorporaciones, sustituciones, etc.)
            destino_articulo = get_destino_articulo(cambio)
            if destino_articulo:
                modified_articles.add(destino_articulo)
                # Si es una derogación individual, marcarla
                if cambio.get("accion") in ["derógase", "derogase"]:
                    derogated_articles.add(destino_articulo)
    
    # Obtener artículos incorporados
    incorporated_articles = get_incorporated_articles(dictamen_data, ley_data)
    
    return MatchResult(
        modified_articles=modified_articles,
        derogated_articles=derogated_articles,
        derogated_chapters=derogated_chapters,
        incorporated_articles=incorporated_articles
    )


def get_cambio_for_articulo(
    dictamen_data: List[Dict[str, Any]],
    numero_articulo: str
) -> Optional[Dict[str, Any]]:
    """
    Encuentra el cambio correspondiente a un artículo específico.
    
    Args:
        dictamen_data: Lista de operaciones del dictamen
        numero_articulo: Número del artículo a buscar
    
    Returns:
        Operación correspondiente o None si no se encuentra
    """
    numero_str = str(numero_articulo)
    for cambio in dictamen_data:
        destino_articulo = get_destino_articulo(cambio)
        if destino_articulo == numero_str:
            return cambio
    return None


def get_incorporated_articles(
    dictamen_data: List[Dict[str, Any]],
    ley_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Obtiene la lista de artículos incorporados (nuevos) que no existen en la ley original.
    
    Args:
        dictamen_data: Lista de operaciones del dictamen
        ley_data: Estructura JSON de la ley
    
    Returns:
        Lista de artículos incorporados con sus datos
    """
    incorporated_articles = []
    
    for cambio in dictamen_data:
        if cambio.get("accion") in ["incorpórase", "incorporase"]:
            destino_articulo = get_destino_articulo(cambio)
            if not destino_articulo:
                continue
            
            # Verificar si el artículo ya existe en la ley original
            exists_in_law = False
            titulos = ley_data.get("ley", {}).get("titulos", [])
            for titulo in titulos:
                if titulo.get("articulos"):
                    if any(str(art.get("numero")) == destino_articulo for art in titulo["articulos"]):
                        exists_in_law = True
                        break
                if titulo.get("capitulos"):
                    for capitulo in titulo["capitulos"]:
                        if capitulo.get("articulos"):
                            if any(str(art.get("numero")) == destino_articulo for art in capitulo["articulos"]):
                                exists_in_law = True
                                break
                    if exists_in_law:
                        break
                if exists_in_law:
                    break
            
            # Solo agregar si no existe en la ley original
            if not exists_in_law:
                # Extraer título del texto_nuevo si está disponible
                titulo = ""
                if cambio.get("texto_nuevo"):
                    titulo_match = re.search(
                        r"ART[ÍI]CULO\s+\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[°º]?-\s*(.+?)(?:\n|$)",
                        cambio["texto_nuevo"],
                        re.IGNORECASE
                    )
                    if titulo_match and titulo_match.group(1):
                        titulo = titulo_match.group(1).strip()
                        # Limpiar el título (puede tener más texto después)
                        titulo = titulo.split('\n')[0].strip()
                
                incorporated_articles.append({
                    "numero": destino_articulo,
                    "titulo": titulo,
                    "texto": cambio.get("texto_nuevo", ""),
                    "isIncorporated": True,
                    "tituloNumero": "I",  # Por defecto, se puede inferir mejor después
                    "tituloNombre": "Disposiciones Generales"  # Por defecto
                })
    
    return incorporated_articles


def get_all_articles(ley_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Obtiene todos los artículos de la ley, incluyendo los de títulos y capítulos.
    
    Args:
        ley_data: Estructura JSON de la ley
    
    Returns:
        Lista de artículos con información de título y capítulo
    """
    all_articles = []
    titulos = ley_data.get("ley", {}).get("titulos", [])
    
    # Obtener artículos de la ley original
    for titulo in titulos:
        if titulo.get("articulos"):
            for articulo in titulo["articulos"]:
                all_articles.append({
                    **articulo,
                    "tituloNombre": titulo.get("nombre", ""),
                    "tituloNumero": titulo.get("numero", "")
                })
        
        if titulo.get("capitulos"):
            for capitulo in titulo["capitulos"]:
                if capitulo.get("articulos"):
                    for articulo in capitulo["articulos"]:
                        all_articles.append({
                            **articulo,
                            "tituloNombre": titulo.get("nombre", ""),
                            "tituloNumero": titulo.get("numero", ""),
                            "capituloNombre": capitulo.get("nombre", ""),
                            "capituloNumero": capitulo.get("numero", "")
                        })
    
    return all_articles


def get_derogated_chapter_articles(
    derogated_chapters: Dict[str, Set[str]],
    ley_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Obtiene los artículos de capítulos derogados, creando artículos sintéticos si es necesario.
    
    Args:
        derogated_chapters: Diccionario de capítulos derogados
        ley_data: Estructura JSON de la ley
    
    Returns:
        Lista de artículos derogados de capítulos
    """
    derogated_articles_list = []
    
    # Buscar capítulos derogados y crear artículos sintéticos si es necesario
    for capitulo_numero, articles_set in derogated_chapters.items():
        for art_id in articles_set:
            # Si es un artículo sintético (formato CAP_VIII_ART_X)
            if art_id.startswith("CAP_"):
                match = re.match(r"CAP_(\w+)_ART_(\d+)", art_id)
                if match:
                    cap_num = match.group(1)
                    art_index = int(match.group(2))
                    
                    # Solo crear artículos sintéticos para Capítulo VIII de Formación Profesional
                    if cap_num == "VIII":
                        # Textos de los artículos del Capítulo VIII según el usuario
                        textos = [
                            "La promoción profesional y la formación en el trabajo, en condiciones igualitarias de acceso y trato será un derecho fundamental para todos los trabajadores y trabajadoras.",
                            "El empleador implementará acciones de formación profesional profesional y/o capacitación con la participación de los trabajadores y con la asistencia de los organismos competentes al Estado.",
                            "La capacitación del trabajador se efectuará de acuerdo a los requerimientos del empleador, a las características de las tareas, a las exigencias de la organización del trabajo y a los medios que le provea el empleador para dicha capacitación.",
                            "La organización sindical que represente a los trabajadores de conformidad a la legislación vigente tendrá derecho a recibir información sobre la evolución de la empresa, sobre innovaciones tecnológicas y organizativas y toda otra que tenga relación con la planificación de acciones de formación y capacitación profesional.",
                            "La organización sindical que represente a los trabajadores de conformidad a la legislación vigente ante innovaciones de base tecnológica y organizativa de la empresa, podrá solicitar al empleador la implementación de acciones de formación profesional para la mejor adecuación del personal al nuevo sistema.",
                            "En el certificado de trabajo que el empleador está obligado a entregar a la extinción del contrato de trabajo deberá constar además de lo prescripto en el artículo 80, la calificación profesional obtenida en el o los puestos de trabajo desempeñados, hubiere o no realizado el trabajador acciones regulares de capacitación.",
                            "El trabajador tendrá derecho a una cantidad de horas del tiempo total anual del trabajo, de acuerdo a lo que se establezca en el convenio colectivo, para realizar, fuera de su lugar de trabajo actividades de formación y/o capacitación que él juzgue de su propio interés."
                        ]
                        
                        if art_index <= len(textos):
                            derogated_articles_list.append({
                                "numero": art_id,
                                "titulo": "",
                                "texto": textos[art_index - 1] if art_index <= len(textos) else "",
                                "isDerogated": True,
                                "tituloNumero": "III",  # El Capítulo VIII está en el Título III
                                "tituloNombre": "De los derechos y obligaciones de las partes",
                                "capituloNumero": "VIII",
                                "capituloNombre": "DE LA FORMACIÓN PROFESIONAL"
                            })
    
    return derogated_articles_list

