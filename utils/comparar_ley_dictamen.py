#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para comparar un JSON de ley con un JSON de dictamen y generar
un JSON de comparación que mantiene la estructura de la ley pero incluye
información sobre los cambios propuestos.

El JSON de salida usa la estructura de la ley como base y agrega metadatos
sobre sustituciones, incorporaciones y derogaciones.
"""

import json
import re
import sys
from typing import Dict, Any, List, Optional, Set
from pathlib import Path


def extract_article_number_from_header(encabezado: str) -> Optional[str]:
    """
    Extrae el número de artículo desde el encabezado del dictamen.
    
    Busca patrones como "incorpórase como artículo X" o "artículo X".
    """
    if not encabezado:
        return None
    
    # Para incorporaciones, buscar "como artículo X" o "artículo X" después de incorpórase
    incorporacion_match = re.search(
        r'incorp[óo]rase\s+como\s+art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)',
        encabezado,
        re.IGNORECASE
    )
    if incorporacion_match:
        return incorporacion_match.group(1).strip()
    
    # Fallback: buscar cualquier "artículo X" con sufijos
    match = re.search(
        r'art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)',
        encabezado,
        re.IGNORECASE
    )
    if match:
        return match[1].strip()
    
    return None


def get_destino_articulo(cambio: Dict[str, Any]) -> Optional[str]:
    """
    Obtiene el número de artículo destino desde un cambio del dictamen.
    
    Prioridad:
    1. destino_articulo explícito
    2. Extraer desde texto_nuevo
    3. Extraer desde encabezado
    """
    # Prioridad 1: destino_articulo explícito
    if cambio.get('destino_articulo'):
        return str(cambio['destino_articulo'])
    
    # Prioridad 2: extraer desde texto_nuevo (más confiable)
    if cambio.get('texto_nuevo'):
        match = re.search(
            r'ART[ÍI]CULO\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?-',
            cambio['texto_nuevo'],
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
    
    # Prioridad 3: extraer desde encabezado
    from_header = extract_article_number_from_header(cambio.get('encabezado', ''))
    return from_header


def normalize_article_number(numero: Any) -> str:
    """Normaliza el número de artículo a string para comparación."""
    if numero is None:
        return ''
    return str(numero).strip()


def find_article_in_ley(
    ley_data: Dict[str, Any],
    numero_articulo: str,
    titulo_numero: Optional[str] = None,
    capitulo_numero: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Busca un artículo en la estructura de la ley.
    
    Retorna el artículo encontrado junto con su contexto (título, capítulo).
    """
    numero_articulo = normalize_article_number(numero_articulo)
    
    for titulo in ley_data.get('ley', {}).get('titulos', []):
        # Si se especificó un título, filtrar por él
        if titulo_numero and normalize_article_number(titulo.get('numero')) != normalize_article_number(titulo_numero):
            continue
        
        # Buscar en artículos directos del título
        if titulo.get('articulos'):
            for articulo in titulo['articulos']:
                if normalize_article_number(articulo.get('numero')) == numero_articulo:
                    return {
                        'articulo': articulo,
                        'titulo': titulo,
                        'capitulo': None
                    }
        
        # Buscar en capítulos
        if titulo.get('capitulos'):
            for capitulo in titulo['capitulos']:
                # Si se especificó un capítulo, filtrar por él
                if capitulo_numero and normalize_article_number(capitulo.get('numero')) != normalize_article_number(capitulo_numero):
                    continue
                
                if capitulo.get('articulos'):
                    for articulo in capitulo['articulos']:
                        if normalize_article_number(articulo.get('numero')) == numero_articulo:
                            return {
                                'articulo': articulo,
                                'titulo': titulo,
                                'capitulo': capitulo
                            }
    
    return None


def find_articles_in_chapter(
    ley_data: Dict[str, Any],
    capitulo_numero: str
) -> List[Dict[str, Any]]:
    """
    Encuentra todos los artículos de un capítulo específico.
    
    Retorna lista de artículos con su contexto.
    """
    articles = []
    capitulo_numero = normalize_article_number(capitulo_numero)
    
    for titulo in ley_data.get('ley', {}).get('titulos', []):
        if titulo.get('capitulos'):
            for capitulo in titulo['capitulos']:
                if normalize_article_number(capitulo.get('numero')) == capitulo_numero:
                    if capitulo.get('articulos'):
                        for articulo in capitulo['articulos']:
                            articles.append({
                                'articulo': articulo,
                                'titulo': titulo,
                                'capitulo': capitulo
                            })
    
    return articles


def extract_title_from_text(texto: str) -> str:
    """
    Extrae el título del artículo desde el texto nuevo.
    
    Busca el patrón "ARTÍCULO X- Título del artículo"
    El título generalmente termina en el primer punto seguido de espacio o salto de línea.
    """
    if not texto:
        return ''
    
    match = re.search(
        r'ART[ÍI]CULO\s+\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[°º]?-\s*(.+?)(?:\.\s+|\n|$)',
        texto,
        re.IGNORECASE
    )
    if match and match.group(1):
        titulo = match.group(1).strip()
        # El título termina en el punto, así que agregarlo si no está
        if not titulo.endswith('.'):
            # Buscar si hay un punto en el título original
            titulo_completo = match.group(0)
            punto_match = re.search(r'\.\s+', titulo_completo)
            if punto_match:
                # El título es hasta el punto
                inicio_titulo = match.start(1)
                fin_titulo = match.start(0) + punto_match.start() + 1
                titulo = texto[inicio_titulo:fin_titulo].strip()
            else:
                # Si no hay punto, tomar solo hasta el salto de línea
                titulo = titulo.split('\n')[0].strip()
        return titulo
    
    return ''


def parse_article_text(texto: str) -> Dict[str, Any]:
    """
    Parsea el texto de un artículo para extraer título, texto principal e incisos.
    
    Retorna un diccionario con 'titulo', 'texto', y opcionalmente 'incisos'.
    """
    if not texto:
        return {'titulo': '', 'texto': ''}
    
    # Extraer título
    titulo = extract_title_from_text(texto)
    
    # Remover solo el encabezado "ARTÍCULO X-" pero preservar el resto del texto
    # El patrón debe capturar: "ARTÍCULO X-" o "ARTÍCULO X°-" seguido del título hasta el primer punto o salto de línea
    # Pero debemos ser más cuidadosos para no cortar el texto que sigue
    
    # Primero, intentar encontrar dónde termina el encabezado
    # El formato típico es: "ARTÍCULO 2°- Ámbito de aplicación. La vigencia..."
    # Queremos remover "ARTÍCULO 2°- Ámbito de aplicación. " pero mantener "La vigencia..."
    
    # Buscar el patrón del encabezado completo
    patron_encabezado = re.compile(
        r'ART[ÍI]CULO\s+\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[°º]?-\s*',
        re.IGNORECASE
    )
    
    texto_limpio = texto
    match_encabezado = patron_encabezado.search(texto_limpio)
    if match_encabezado:
        # Encontrar dónde termina el título (después del guion, hasta el primer punto seguido de espacio)
        inicio_texto = match_encabezado.end()
        # Buscar el final del título - generalmente termina con un punto seguido de espacio
        fin_titulo_match = re.search(r'\.\s+', texto_limpio[inicio_texto:])
        if fin_titulo_match:
            # El texto real comienza después del punto y espacio
            inicio_texto_real = inicio_texto + fin_titulo_match.end()
            texto_limpio = texto_limpio[inicio_texto_real:]
        else:
            # Si no hay punto seguido de espacio, buscar solo punto
            fin_titulo_match = re.search(r'\.', texto_limpio[inicio_texto:])
            if fin_titulo_match:
                # El texto real comienza después del punto (puede haber salto de línea)
                inicio_texto_real = inicio_texto + fin_titulo_match.end()
                # Saltar espacios y saltos de línea
                while inicio_texto_real < len(texto_limpio) and texto_limpio[inicio_texto_real] in ' \n':
                    inicio_texto_real += 1
                texto_limpio = texto_limpio[inicio_texto_real:]
            else:
                # Si no hay punto, buscar salto de línea
                fin_titulo_match = re.search(r'\n', texto_limpio[inicio_texto:])
                if fin_titulo_match:
                    inicio_texto_real = inicio_texto + fin_titulo_match.end()
                    texto_limpio = texto_limpio[inicio_texto_real:]
                else:
                    # Si no hay punto ni salto de línea, remover solo el encabezado
                    texto_limpio = texto_limpio[inicio_texto:]
    
    texto_limpio = texto_limpio.strip()
    
    # Extraer incisos
    incisos = []
    patron_inciso = re.compile(
        r'([a-z])\)\s+([^a-z\)]+?)(?=\n|$|([a-z])\)|ARTICULO)',
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    matches = list(patron_inciso.finditer(texto_limpio))
    if matches:
        for match in matches:
            letra = match.group(1).lower()
            texto_inciso = match.group(2).strip()
            if texto_inciso:
                incisos.append({
                    'letra': letra,
                    'texto': texto_inciso
                })
        
        # Remover incisos del texto principal
        for match in reversed(matches):
            texto_limpio = texto_limpio[:match.start()] + texto_limpio[match.end():]
        texto_limpio = texto_limpio.strip()
    
    result = {
        'titulo': titulo,
        'texto': texto_limpio
    }
    
    if incisos:
        result['incisos'] = incisos
    
    return result


def process_dictamen_changes(dictamen_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Procesa los cambios del dictamen y crea un mapa estructurado.
    
    Retorna un diccionario con:
    - cambios_por_articulo: {numero_articulo: cambio}
    - incorporaciones: [cambios de incorporación]
    - derogaciones_articulos: Set de números de artículos derogados
    - derogaciones_capitulos: {numero_capitulo: Set de artículos}
    """
    cambios_por_articulo = {}
    incorporaciones = []
    derogaciones_articulos: Set[str] = set()
    derogaciones_capitulos: Dict[str, Set[str]] = {}
    
    for cambio in dictamen_data:
        accion = cambio.get('accion', '').lower()
        destino_capitulo = cambio.get('destino_capitulo')
        
        # Procesar derogaciones de capítulos completos
        if destino_capitulo:
            capitulo_numero = str(destino_capitulo)
            derogaciones_capitulos[capitulo_numero] = set()
            # Los artículos específicos se marcarán cuando se procese la ley
        
        # Procesar otros cambios
        destino_articulo = get_destino_articulo(cambio)
        if destino_articulo:
            destino_articulo = normalize_article_number(destino_articulo)
            
            if accion in ('incorpórase', 'incorporase'):
                incorporaciones.append({
                    'cambio': cambio,
                    'numero': destino_articulo
                })
            elif accion in ('derógase', 'derogase'):
                derogaciones_articulos.add(destino_articulo)
                cambios_por_articulo[destino_articulo] = {
                    'tipo': 'derogacion',
                    'cambio': cambio
                }
            elif accion in ('sustitúyese', 'sustituyese'):
                cambios_por_articulo[destino_articulo] = {
                    'tipo': 'sustitucion',
                    'cambio': cambio
                }
    
    return {
        'cambios_por_articulo': cambios_por_articulo,
        'incorporaciones': incorporaciones,
        'derogaciones_articulos': derogaciones_articulos,
        'derogaciones_capitulos': derogaciones_capitulos
    }


def apply_changes_to_article(
    articulo_original: Dict[str, Any],
    cambios: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Aplica los cambios del dictamen a un artículo de la ley.
    
    Retorna el artículo con metadatos de comparación.
    """
    numero = normalize_article_number(articulo_original.get('numero'))
    cambio_info = cambios.get('cambios_por_articulo', {}).get(numero)
    
    # Crear copia del artículo original
    articulo_comparado = articulo_original.copy()
    
    if cambio_info:
        cambio = cambio_info['cambio']
        tipo = cambio_info['tipo']
        
        if tipo == 'sustitucion':
            # Parsear el texto nuevo
            texto_nuevo = cambio.get('texto_nuevo', '')
            parsed = parse_article_text(texto_nuevo)
            
            articulo_comparado['estado'] = 'sustituido'
            articulo_comparado['texto_original'] = articulo_original.get('texto', '')
            articulo_comparado['texto_nuevo'] = parsed.get('texto', '')
            
            # Actualizar título si está en el texto nuevo
            if parsed.get('titulo'):
                articulo_comparado['titulo_nuevo'] = parsed['titulo']
            
            # Actualizar incisos si existen
            if parsed.get('incisos'):
                articulo_comparado['incisos_nuevos'] = parsed['incisos']
                articulo_comparado['incisos_originales'] = articulo_original.get('incisos', [])
            
            articulo_comparado['accion'] = cambio.get('accion', 'sustitúyese')
            articulo_comparado['dictamen_articulo'] = cambio.get('dictamen_articulo')
        
        elif tipo == 'derogacion':
            articulo_comparado['estado'] = 'derogado'
            articulo_comparado['accion'] = cambio.get('accion', 'derógase')
            articulo_comparado['dictamen_articulo'] = cambio.get('dictamen_articulo')
    else:
        articulo_comparado['estado'] = 'sin_cambios'
    
    return articulo_comparado


def find_titulo_for_article(
    ley_data: Dict[str, Any],
    numero_articulo: str
) -> Optional[Dict[str, Any]]:
    """
    Encuentra el título donde debería ir un artículo basándose en los números
    de artículos existentes en cada título.
    
    Retorna el título encontrado o None si no se puede determinar.
    """
    numero_articulo = normalize_article_number(numero_articulo)
    
    # Extraer número base para comparación
    def extract_base_number(num_str):
        match = re.match(r'^(\d+)', num_str)
        return int(match.group(1)) if match else 0
    
    try:
        target_base = extract_base_number(numero_articulo)
    except:
        return None
    
    # Recopilar todos los números de artículos por título
    titulos_ranges = []
    
    for titulo in ley_data.get('ley', {}).get('titulos', []):
        min_num = float('inf')
        max_num = 0
        has_articles = False
        
        # Buscar en artículos directos del título
        if titulo.get('articulos'):
            for articulo in titulo['articulos']:
                art_num = normalize_article_number(articulo.get('numero', ''))
                try:
                    art_base = extract_base_number(art_num)
                    min_num = min(min_num, art_base)
                    max_num = max(max_num, art_base)
                    has_articles = True
                except:
                    continue
        
        # Buscar en capítulos
        if titulo.get('capitulos'):
            for capitulo in titulo['capitulos']:
                if capitulo.get('articulos'):
                    for articulo in capitulo['articulos']:
                        art_num = normalize_article_number(articulo.get('numero', ''))
                        try:
                            art_base = extract_base_number(art_num)
                            min_num = min(min_num, art_base)
                            max_num = max(max_num, art_base)
                            has_articles = True
                        except:
                            continue
        
        if has_articles:
            titulos_ranges.append({
                'titulo': titulo,
                'min': min_num,
                'max': max_num
            })
    
    # Buscar el título cuyo rango contiene el número objetivo
    for tr in titulos_ranges:
        if tr['min'] <= target_base <= tr['max']:
            return tr['titulo']
    
    # Si no está en ningún rango, buscar el título con el máximo más cercano
    # pero menor al objetivo (para artículos que van después del último artículo)
    best_titulo = None
    best_max = -1
    
    for tr in titulos_ranges:
        if tr['max'] < target_base and tr['max'] > best_max:
            best_max = tr['max']
            best_titulo = tr['titulo']
    
    if best_titulo:
        return best_titulo
    
    # Si no se encontró, usar el último título con artículos
    if titulos_ranges:
        return titulos_ranges[-1]['titulo']
    
    return None


def process_incorporated_articles(
    incorporaciones: List[Dict[str, Any]],
    ley_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Procesa las incorporaciones y determina dónde deben insertarse.
    
    Retorna lista de artículos incorporados con su contexto (título donde deben ir).
    """
    articulos_incorporados = []
    
    for inc in incorporaciones:
        cambio = inc['cambio']
        numero = inc['numero']
        
        # Verificar si el artículo ya existe en la ley
        existe = find_article_in_ley(ley_data, numero) is not None
        
        if not existe:
            # Parsear el texto nuevo
            texto_nuevo = cambio.get('texto_nuevo', '')
            parsed = parse_article_text(texto_nuevo)
            
            # Encontrar el título donde debería ir este artículo
            titulo_destino = find_titulo_for_article(ley_data, numero)
            
            articulo_incorporado = {
                'numero': numero,
                'titulo': parsed.get('titulo', ''),
                'texto': parsed.get('texto', ''),
                'estado': 'incorporado',
                'accion': cambio.get('accion', 'incorpórase'),
                'dictamen_articulo': cambio.get('dictamen_articulo'),
                'titulo_destino_numero': titulo_destino.get('numero') if titulo_destino else None
            }
            
            if parsed.get('incisos'):
                articulo_incorporado['incisos'] = parsed['incisos']
            
            articulos_incorporados.append(articulo_incorporado)
    
    return articulos_incorporados


def comparar_ley_dictamen(
    ley_path: str,
    dictamen_path: str,
    output_path: str
) -> None:
    """
    Función principal que compara una ley con un dictamen y genera un JSON de comparación.
    
    Args:
        ley_path: Ruta al JSON de la ley
        dictamen_path: Ruta al JSON del dictamen
        output_path: Ruta donde guardar el JSON de comparación
    """
    # Cargar datos
    with open(ley_path, 'r', encoding='utf-8') as f:
        ley_data = json.load(f)
    
    with open(dictamen_path, 'r', encoding='utf-8') as f:
        dictamen_data = json.load(f)
    
    # Procesar cambios del dictamen
    cambios = process_dictamen_changes(dictamen_data)
    
    # Crear estructura de comparación basada en la ley
    comparacion = {
        'ley': ley_data.get('ley', {}).copy(),
        'metadatos': {
            'ley_origen': str(Path(ley_path).name),
            'dictamen_origen': str(Path(dictamen_path).name),
            'total_sustituciones': len([c for c in cambios['cambios_por_articulo'].values() if c['tipo'] == 'sustitucion']),
            'total_incorporaciones': len(cambios['incorporaciones']),
            'total_derogaciones': len(cambios['derogaciones_articulos']),
            'capitulos_derogados': list(cambios['derogaciones_capitulos'].keys())
        }
    }
    
    # Procesar títulos
    comparacion['ley']['titulos'] = []
    
    for titulo in ley_data.get('ley', {}).get('titulos', []):
        titulo_comparado = titulo.copy()
        titulo_comparado['articulos'] = []
        titulo_comparado['capitulos'] = []
        
        # Procesar artículos directos del título
        if titulo.get('articulos'):
            for articulo in titulo['articulos']:
                articulo_comparado = apply_changes_to_article(articulo, cambios)
                titulo_comparado['articulos'].append(articulo_comparado)
        
        # Procesar capítulos
        if titulo.get('capitulos'):
            for capitulo in titulo['capitulos']:
                capitulo_comparado = capitulo.copy()
                capitulo_numero = normalize_article_number(capitulo.get('numero'))
                
                # Verificar si el capítulo completo fue derogado
                if capitulo_numero in cambios['derogaciones_capitulos']:
                    capitulo_comparado['estado'] = 'derogado'
                    capitulo_comparado['articulos'] = []
                    
                    # Marcar todos los artículos como derogados
                    if capitulo.get('articulos'):
                        for articulo in capitulo['articulos']:
                            articulo_derogado = articulo.copy()
                            articulo_derogado['estado'] = 'derogado'
                            articulo_derogado['accion'] = 'derógase (capítulo completo)'
                            capitulo_comparado['articulos'].append(articulo_derogado)
                else:
                    # Procesar artículos del capítulo
                    capitulo_comparado['articulos'] = []
                    if capitulo.get('articulos'):
                        for articulo in capitulo['articulos']:
                            articulo_comparado = apply_changes_to_article(articulo, cambios)
                            capitulo_comparado['articulos'].append(articulo_comparado)
                
                titulo_comparado['capitulos'].append(capitulo_comparado)
        
        comparacion['ley']['titulos'].append(titulo_comparado)
    
    # Procesar artículos incorporados y agregarlos en sus títulos correspondientes
    articulos_incorporados = process_incorporated_articles(
        cambios['incorporaciones'],
        ley_data
    )
    
    if articulos_incorporados:
        # Función para ordenar artículos por número
        def sort_key(art):
            num = normalize_article_number(art.get('numero', ''))
            # Extraer número base y sufijo para ordenar correctamente
            match = re.match(r'^(\d+)(?:\s*(bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?', num, re.IGNORECASE)
            if match:
                base_num = int(match.group(1))
                suffix = match.group(2).lower() if match.group(2) else ''
                suffix_order = {
                    '': 0, 'bis': 1, 'ter': 2, 'quater': 3, 'quinquies': 4,
                    'sexies': 5, 'septies': 6, 'octies': 7, 'nonies': 8, 'decies': 9
                }
                return (base_num, suffix_order.get(suffix, 0))
            try:
                base_num = int(re.match(r'(\d+)', num).group(1))
                return (base_num, 0)
            except:
                return (999999, 0)  # Números no parseables al final
        
        # Agrupar artículos incorporados por título destino
        incorporados_por_titulo = {}
        for art_inc in articulos_incorporados:
            titulo_num = art_inc.get('titulo_destino_numero')
            if titulo_num:
                if titulo_num not in incorporados_por_titulo:
                    incorporados_por_titulo[titulo_num] = []
                incorporados_por_titulo[titulo_num].append(art_inc)
        
        # Insertar artículos incorporados en sus títulos correspondientes
        for titulo in comparacion['ley']['titulos']:
            titulo_num = str(titulo.get('numero'))
            if titulo_num in incorporados_por_titulo:
                # Intentar insertar en capítulos primero
                inserted_in_chapter = False
                if titulo.get('capitulos'):
                    for capitulo in titulo['capitulos']:
                        if capitulo.get('articulos'):
                            # Verificar si algún artículo incorporado debería ir en este capítulo
                            for art_inc in incorporados_por_titulo[titulo_num]:
                                art_num = normalize_article_number(art_inc.get('numero', ''))
                                # Buscar el artículo base (sin sufijo) en este capítulo
                                for articulo in capitulo['articulos']:
                                    art_existing = normalize_article_number(articulo.get('numero', ''))
                                    # Si encontramos un artículo con número base igual o cercano
                                    try:
                                        base_inc = int(re.match(r'^(\d+)', art_num).group(1))
                                        base_existing = int(re.match(r'^(\d+)', art_existing).group(1))
                                        # Si el artículo incorporado tiene el mismo número base o es "bis" de un artículo existente
                                        if base_inc == base_existing or (art_num.endswith('bis') and base_inc == base_existing):
                                            # Insertar en este capítulo
                                            art_inc_clean = {k: v for k, v in art_inc.items() 
                                                           if k != 'titulo_destino_numero'}
                                            capitulo['articulos'].append(art_inc_clean)
                                            inserted_in_chapter = True
                                            break
                                    except:
                                        continue
                                if inserted_in_chapter:
                                    break
                
                # Si no se insertó en un capítulo, agregar a artículos directos del título
                if not inserted_in_chapter:
                    if 'articulos' not in titulo:
                        titulo['articulos'] = []
                    
                    # Agregar artículos incorporados que no se insertaron en capítulos
                    for art_inc in incorporados_por_titulo[titulo_num]:
                        # Verificar si ya fue insertado en un capítulo
                        art_num = normalize_article_number(art_inc.get('numero', ''))
                        already_inserted = False
                        if titulo.get('capitulos'):
                            for capitulo in titulo['capitulos']:
                                if capitulo.get('articulos'):
                                    for art in capitulo['articulos']:
                                        if normalize_article_number(art.get('numero', '')) == art_num:
                                            already_inserted = True
                                            break
                                    if already_inserted:
                                        break
                        
                        if not already_inserted:
                            art_inc_clean = {k: v for k, v in art_inc.items() 
                                           if k != 'titulo_destino_numero'}
                            titulo['articulos'].append(art_inc_clean)
                
                # Ordenar todos los artículos del título por número
                if titulo.get('articulos'):
                    titulo['articulos'].sort(key=sort_key)
                
                # También ordenar artículos dentro de capítulos
                if titulo.get('capitulos'):
                    for capitulo in titulo['capitulos']:
                        if capitulo.get('articulos'):
                            capitulo['articulos'].sort(key=sort_key)
    
    # Guardar resultado
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comparacion, f, ensure_ascii=False, indent=2)
    
    print(f"Comparación generada exitosamente: {output_path}")
    print(f"  - Sustituciones: {len([c for c in cambios['cambios_por_articulo'].values() if c['tipo'] == 'sustitucion'])}")
    print(f"  - Incorporaciones: {len(articulos_incorporados)}")
    print(f"  - Derogaciones: {len(cambios['derogaciones_articulos'])}")


def main():
    """Función principal del script."""
    if len(sys.argv) < 4:
        print("Uso: python comparar_ley_dictamen.py <ley.json> <dictamen.json> <output.json>")
        print("\nEjemplo:")
        print("  python comparar_ley_dictamen.py data/ley_contrato_trabajo_oficial_completa.json \\")
        print("                                    data/dictamen_modernizacion_laboral_titulo_I.json \\")
        print("                                    data/comparacion_titulo_I.json")
        sys.exit(1)
    
    ley_path = sys.argv[1]
    dictamen_path = sys.argv[2]
    output_path = sys.argv[3]
    
    # Validar que los archivos existan
    if not Path(ley_path).exists():
        print(f"Error: No se encuentra el archivo de ley: {ley_path}")
        sys.exit(1)
    
    if not Path(dictamen_path).exists():
        print(f"Error: No se encuentra el archivo de dictamen: {dictamen_path}")
        sys.exit(1)
    
    try:
        comparar_ley_dictamen(ley_path, dictamen_path, output_path)
    except Exception as e:
        print(f"Error al procesar la comparación: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

