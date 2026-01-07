#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script final para convertir exhaustivamente el JSON oficial de la Ley de Contrato de Trabajo
"""

import json
import re

# Leer el JSON oficial
with open('view-document.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

doc_data = json.loads(data['data'])
document = doc_data['document']
metadata = document['metadata']
content = document['content']

def limpiar_texto(texto):
    """Limpia el texto de etiquetas HTML/XML"""
    if not texto:
        return ""
    # Remover etiquetas [[p]], [[/p]], [[r uuid:...]], etc.
    texto = re.sub(r'\[\[/?(p|r|/r)[^\]]*\]\]', '', texto)
    # Remover referencias [[r uuid:...]]
    texto = re.sub(r'\[\[r[^\]]+\]\]', '', texto)
    # Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def procesar_incisos(texto):
    """Extrae incisos del texto del artículo"""
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

def procesar_articulo(art):
    """Procesa un artículo con todos sus metadatos"""
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
print(f"Procesando {len(segmentos)} segmentos...")

for segmento in segmentos:
    titulo_particion = segmento.get('titulo-particion', '')
    
    # Detectar TÍTULO
    match_titulo = re.match(r'TITULO\s+([IVXLCDM]+)[\.\s\-]*(.+)', titulo_particion, re.IGNORECASE)
    if match_titulo:
        numero_titulo = match_titulo.group(1)
        nombre_titulo = match_titulo.group(2).strip()
        
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
                match_cap = (re.match(r'CAPITULO\s+([IVXLCDM]+)[\.\s\-]*(.+)', cap_titulo, re.IGNORECASE) or
                            re.match(r'Cap[íi]tulo\s+([IVXLCDM]+)[\.\s\-]*(.+)', cap_titulo, re.IGNORECASE) or
                            re.match(r'Capitulo\s+([IVXLCDM]+)[\.\s\-]*(.+)', cap_titulo, re.IGNORECASE))
                
                if match_cap:
                    numero_cap = match_cap.group(1)
                    nombre_cap = match_cap.group(2).strip()
                    
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
                    
                    titulo_obj['capitulos'].append(capitulo_obj)
        
        ley_estructurada['ley']['titulos'].append(titulo_obj)

# Limpiar arrays vacíos
def limpiar_estructura(obj):
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if isinstance(obj[key], list) and not obj[key]:
                del obj[key]
            else:
                limpiar_estructura(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            limpiar_estructura(item)

limpiar_estructura(ley_estructurada)

# Guardar JSON completo
with open('ley_contrato_trabajo_oficial_completa.json', 'w', encoding='utf-8') as f:
    json.dump(ley_estructurada, f, ensure_ascii=False, indent=2)

# Estadísticas
print("=" * 70)
print("CONVERSIÓN COMPLETA DEL JSON OFICIAL")
print("=" * 70)
print(f"Archivo generado: ley_contrato_trabajo_oficial_completa.json")
print(f"Total de títulos: {len(ley_estructurada['ley']['titulos'])}")

total_articulos = 0
total_capitulos = 0
total_incisos = 0
articulos_con_referencias = 0

for titulo in ley_estructurada['ley']['titulos']:
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
for titulo in ley_estructurada['ley']['titulos']:
    arts_titulo = len(titulo.get('articulos', []))
    arts_caps = sum(len(cap.get('articulos', [])) for cap in titulo.get('capitulos', []))
    print(f"  Título {titulo['numero']}: {arts_titulo} + {arts_caps} = {arts_titulo + arts_caps} arts")
print("=" * 70)

