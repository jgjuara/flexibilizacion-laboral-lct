#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser para convertir el JSON oficial de la Ley de Contrato de Trabajo desde SAIJ
a un formato estructurado.

Convierte el JSON oficial (view-document.json) a un formato normalizado
con títulos, capítulos y artículos estructurados.
"""

import json
import re
from typing import Dict, Any, List, Optional


def limpiar_texto(texto: str) -> str:
    """Limpia el texto de etiquetas HTML/XML."""
    if not texto:
        return ""
    # Remover etiquetas [[p]], [[/p]], [[r uuid:...]], etc.
    texto = re.sub(r'\[\[/?(p|r|/r)[^\]]*\]\]', '', texto)
    # Remover referencias [[r uuid:...]]
    texto = re.sub(r'\[\[r[^\]]+\]\]', '', texto)
    # Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def procesar_incisos(texto: str) -> List[Dict[str, str]]:
    """Extrae incisos del texto del artículo."""
    incisos = []
    if not texto:
        return incisos
    
    # Primero limpiar el texto pero preservar estructura de incisos
    texto_limpio = texto
    
    # Buscar patrones: a) texto, b) texto, etc.
    # Los incisos pueden estar en líneas separadas o en el mismo párrafo
    patron = re.compile(r'([a-z])\)\s+([^a-z\)]+?)(?=\n|$|([a-z])\)|ARTICULO|\[\[)', 
                       re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    # También buscar después de [[p]]
    patron2 = re.compile(r'\[\[p\]\]\s*([a-z])\)\s+([^\[]+?)(?=\[\[|$|([a-z])\)|ARTICULO)', 
                        re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    matches = list(patron.finditer(texto_limpio)) + list(patron2.finditer(texto_limpio))
    
    for match in matches:
        letra = match.group(1).lower()
        texto_inciso = match.group(2).strip()
        texto_inciso = limpiar_texto(texto_inciso)
        if texto_inciso:
            incisos.append({
                "letra": letra,
                "texto": texto_inciso
            })
    
    # Si no encontró con regex, buscar manualmente
    if not incisos:
        # Dividir por [[p]] y buscar incisos
        partes = re.split(r'\[\[p\]\]', texto_limpio)
        for parte in partes:
            parte = parte.replace('[[/p]]', '').strip()
            match_inciso = re.match(r'^([a-z])\)\s+(.+)$', parte, re.IGNORECASE | re.DOTALL)
            if match_inciso:
                incisos.append({
                    "letra": match_inciso.group(1).lower(),
                    "texto": limpiar_texto(match_inciso.group(2))
                })
    
    return incisos


def procesar_articulo(art: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Procesa un artículo con todos sus metadatos."""
    if not art:
        return None
    
    numero_art = str(art.get('numero-articulo', ''))
    titulo_art = limpiar_texto(art.get('titulo-articulo', ''))
    texto_art = limpiar_texto(art.get('texto', ''))
    
    articulo = {
        "numero": numero_art,
        "titulo": titulo_art,
        "texto": texto_art
    }
    
    # Extraer incisos del texto original (antes de limpiar)
    texto_original = art.get('texto', '')
    incisos = procesar_incisos(texto_original)
    if incisos:
        articulo['incisos'] = incisos
    
    # Procesar referencias normativas
    if 'antecedentes' in art:
        refs = art['antecedentes']
        if isinstance(refs, dict) and 'referencia-normativa' in refs:
            ref_norm = refs['referencia-normativa']
            articulo['antecedentes'] = ref_norm if isinstance(ref_norm, list) else [ref_norm]
        elif isinstance(refs, list):
            articulo['antecedentes'] = refs
    
    if 'modificado-por' in art:
        modif = art['modificado-por']
        if isinstance(modif, dict) and 'referencia-normativa' in modif:
            ref_norm = modif['referencia-normativa']
            articulo['modificado_por'] = ref_norm if isinstance(ref_norm, list) else [ref_norm]
        elif isinstance(modif, list):
            articulo['modificado_por'] = modif
    
    if 'derogado-por' in art:
        der = art['derogado-por']
        if isinstance(der, dict) and 'referencia-normativa' in der:
            articulo['derogado_por'] = der['referencia-normativa']
        else:
            articulo['derogado_por'] = der
    
    if 'observado-por' in art:
        obs = art['observado-por']
        if isinstance(obs, dict) and 'referencia-normativa' in obs:
            ref_norm = obs['referencia-normativa']
            articulo['observado_por'] = ref_norm if isinstance(ref_norm, list) else [ref_norm]
        elif isinstance(obs, list):
            articulo['observado_por'] = obs
    
    if 'referencias-normativas' in art:
        refs = art['referencias-normativas']
        if isinstance(refs, dict) and 'referencia-normativa' in refs:
            ref_norm = refs['referencia-normativa']
            articulo['referencias_normativas'] = ref_norm if isinstance(ref_norm, list) else [ref_norm]
        elif isinstance(refs, list):
            articulo['referencias_normativas'] = refs
    
    if 'observa-a' in art:
        articulo['observa_a'] = art['observa-a']
    
    if 'informacion-vinculada' in art:
        articulo['informacion_vinculada'] = art['informacion-vinculada']
    
    return articulo


def limpiar_estructura(obj: Any) -> None:
    """Elimina arrays vacíos de la estructura."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if isinstance(obj[key], list) and not obj[key]:
                del obj[key]
            else:
                limpiar_estructura(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            limpiar_estructura(item)


def parse_saij_json(input_path: str) -> Dict[str, Any]:
    """
    Parsea el JSON oficial de SAIJ y retorna la estructura normalizada.
    
    Args:
        input_path: Ruta al archivo JSON de SAIJ (view-document.json)
    
    Returns:
        Diccionario con la estructura de la ley normalizada
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    raw_data = data.get('data')
    if isinstance(raw_data, str):
        doc_data = json.loads(raw_data)
    else:
        doc_data = raw_data

    document = doc_data['document']
    metadata = document['metadata']
    content = document['content']

    # Crear estructura principal
    ley_estructurada = {
        "ley": {
            "nombre": content.get('titulo-norma', ''),
            "numero": str(content.get('numero-norma', '')),
            "tipo": content.get('tipo-norma', {}),
            "fecha": content.get('fecha', ''),
            "texto_ordenado": content.get('texto-ordenado', ''),
            "estado": content.get('estado', ''),
            "jurisdiccion": content.get('jurisdiccion', {}),
            "publicacion": content.get('publicacion-codificada', {}),
            "lugar_sancion": content.get('lugar-sancion', ''),
            "identificacion_coloquial": content.get('identificacion-coloquial', {}),
            "metadatos": {
                "uuid": metadata.get('uuid', ''),
                "document_content_type": metadata.get('document-content-type', ''),
                "timestamp": metadata.get('timestamp', ''),
                "friendly_url": metadata.get('friendly-url', {}),
                "id_infojus": content.get('id-infojus', ''),
                "fecha_umod": content.get('fecha-umod', '')
            },
            "decretos_reglamentarios": content.get('decreto-reglamentario', {}).get('referencia-normativa', []),
            "generalidades": content.get('generalidades', {}),
            "descriptores": content.get('descriptores', {}),
            "sumario": content.get('sumario', {}),
            "titulos": []
        }
    }

    # Procesar todos los segmentos
    segmentos = content.get('segmento', [])

    # Si hay artículos directos en content (fuera de segmentos), agregarlos a un título genérico
    if 'articulo' in content:
        titulo_obj = {
            "numero": "S/N",
            "nombre": "Artículos Generales",
            "capitulos": [],
            "articulos": []
        }
        arts = content['articulo']
        if not isinstance(arts, list):
            arts = [arts]
        for art in arts:
            art_procesado = procesar_articulo(art)
            if art_procesado:
                titulo_obj['articulos'].append(art_procesado)
        ley_estructurada['ley']['titulos'].append(titulo_obj)

    for segmento in segmentos:
        titulo_particion = segmento.get('titulo-particion', '')
        
        # Detectar TÍTULO con regex más permisivo
        match_titulo = re.match(r'(?:TITULO|TÍTULO)\s+([IVXLCDM0-9]+|PRELIMINAR|UNICO|ÚNICO)[\.\s\-]*(.*)', titulo_particion, re.IGNORECASE)
        
        if match_titulo:
            numero_titulo = match_titulo.group(1)
            nombre_titulo = match_titulo.group(2).strip()
        else:
            # Fallback para segmentos que no son títulos pero tienen artículos
            # Usar el nombre de partición como nombre de título o "Sección"
            numero_titulo = "S/N"
            nombre_titulo = titulo_particion.strip() if titulo_particion else "Sin Título"

        titulo_obj = {
            "numero": numero_titulo,
            "nombre": nombre_titulo,
            "capitulos": [],
            "articulos": []
        }
        
        # Procesar artículos directos
        if 'articulo' in segmento:
            arts = segmento['articulo']
            if not isinstance(arts, list):
                arts = [arts]
            for art in arts:
                art_procesado = procesar_articulo(art)
                if art_procesado:
                    titulo_obj['articulos'].append(art_procesado)
        
        # Procesar sub-segmentos (capítulos)
        if 'segmento' in segmento:
            for sub_seg in segmento['segmento']:
                cap_titulo = sub_seg.get('titulo-particion', '')
                # Múltiples patrones para capítulos
                match_cap = (re.match(r'\*?\s*(?:CAPITULO|CAPÍTULO)\s+([IVXLCDM0-9]+)[\.\s\-]*(.*)', cap_titulo, re.IGNORECASE))
                
                if match_cap:
                    numero_cap = match_cap.group(1)
                    nombre_cap = match_cap.group(2).strip()
                else:
                    numero_cap = "S/N"
                    nombre_cap = cap_titulo.strip()

                capitulo_obj = {
                    "numero": numero_cap,
                    "nombre": nombre_cap,
                    "articulos": []
                }
                
                # Procesar artículos del capítulo
                if 'articulo' in sub_seg:
                    arts = sub_seg['articulo']
                    if not isinstance(arts, list):
                        arts = [arts]
                    for art in arts:
                        art_procesado = procesar_articulo(art)
                        if art_procesado:
                            capitulo_obj['articulos'].append(art_procesado)
                
                # Solo agregar capítulo si tiene artículos o nombre relevante
                if capitulo_obj['articulos'] or match_cap:
                    titulo_obj['capitulos'].append(capitulo_obj)
        
        # Solo agregar título si tiene contenido
        if titulo_obj['articulos'] or titulo_obj['capitulos']:
            ley_estructurada['ley']['titulos'].append(titulo_obj)

    # Limpiar arrays vacíos
    limpiar_estructura(ley_estructurada)

    return ley_estructurada


def main() -> None:
    """CLI para convertir JSON de SAIJ."""
    import argparse
    
    ap = argparse.ArgumentParser(description="Convierte JSON oficial de SAIJ a formato estructurado.")
    ap.add_argument("input", help="Ruta al archivo JSON de SAIJ (view-document.json)")
    ap.add_argument("-o", "--output", default="ley_contrato_trabajo_oficial_completa.json", 
                    help="Archivo JSON de salida")
    ap.add_argument("--pretty", action="store_true", help="JSON con indentación")
    args = ap.parse_args()

    print(f"Procesando {args.input}...")
    ley_estructurada = parse_saij_json(args.input)

    # Guardar JSON completo
    with open(args.output, 'w', encoding='utf-8') as f:
        if args.pretty:
            json.dump(ley_estructurada, f, ensure_ascii=False, indent=2)
        else:
            json.dump(ley_estructurada, f, ensure_ascii=False)

    # Estadísticas
    print("=" * 70)
    print("CONVERSIÓN COMPLETA DEL JSON OFICIAL")
    print("=" * 70)
    print(f"Archivo generado: {args.output}")
    titulos_lista = ley_estructurada['ley'].get('titulos', [])
    print(f"Total de títulos: {len(titulos_lista)}")

    total_articulos = 0
    total_capitulos = 0
    total_incisos = 0
    articulos_con_referencias = 0

    for titulo in titulos_lista:
        total_articulos += len(titulo.get('articulos', []))
        total_capitulos += len(titulo.get('capitulos', []))
        
        for art in titulo.get('articulos', []):
            total_incisos += len(art.get('incisos', []))
            if any(key in art for key in ['antecedentes', 'modificado_por', 'derogado_por', 'observado_por', 'referencias_normativas']):
                articulos_con_referencias += 1
        
        for cap in titulo.get('capitulos', []):
            total_articulos += len(cap.get('articulos', []))
            for art in cap.get('articulos', []):
                total_incisos += len(art.get('incisos', []))
                if any(key in art for key in ['antecedentes', 'modificado_por', 'derogado_por', 'observado_por', 'referencias_normativas']):
                    articulos_con_referencias += 1

    print(f"Total de capítulos: {total_capitulos}")
    print(f"Total de artículos: {total_articulos}")
    print(f"Total de incisos: {total_incisos}")
    print(f"Artículos con referencias normativas: {articulos_con_referencias}")
    print("=" * 70)
    print("\nEstructura por título:")
    for titulo in titulos_lista:
        arts_titulo = len(titulo.get('articulos', []))
        capitulos = titulo.get('capitulos', [])
        
        # Construir lista de artículos por capítulo
        partes = []
        if arts_titulo > 0:
            partes.append(str(arts_titulo))
        
        for cap in capitulos:
            arts_cap = len(cap.get('articulos', []))
            if arts_cap > 0:
                partes.append(str(arts_cap))
        
        total = arts_titulo + sum(len(cap.get('articulos', [])) for cap in capitulos)
        if partes:
            descripcion = " + ".join(partes)
            print(f"  Título {titulo['numero']}: {descripcion} = {total} arts")
        else:
            print(f"  Título {titulo['numero']}: 0 arts")
    print("=" * 70)


if __name__ == '__main__':
    main()

