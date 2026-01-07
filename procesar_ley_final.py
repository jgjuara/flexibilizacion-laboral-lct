#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import re
import sys

# Configurar encoding para salida
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Leer el archivo de texto
try:
    with open('LEY DE CONTRATO DE TRABAJO.txt', 'r', encoding='utf-8') as f:
        contenido = f.read()
except UnicodeDecodeError:
    with open('LEY DE CONTRATO DE TRABAJO.txt', 'r', encoding='latin-1') as f:
        contenido = f.read()

# Estructura principal
ley = {
    "ley": {
        "nombre": "LEY DE CONTRATO DE TRABAJO",
        "numero": "20.744",
        "año": "1976",
        "texto_ordenado": "1976",
        "titulos": []
    }
}

# Dividir por líneas y limpiar números de línea
lineas_raw = contenido.split('\n')
lineas = []

for linea in lineas_raw:
    # Eliminar número de línea al inicio (formato: "   123|texto")
    match = re.match(r'^\s*\d+\|(.*)$', linea)
    if match:
        lineas.append(match.group(1))
    else:
        lineas.append(linea)

# Variables de estado
titulo_actual = None
capitulo_actual = None
articulo_actual = None
texto_acumulado = ""

# Patrones regex
patron_titulo = re.compile(r'^TITULO\s+([IVXLCDM]+)\s*$', re.IGNORECASE)
patron_capitulo = re.compile(r'^CAPITULO\s+([IVXLCDM]+)\s*$', re.IGNORECASE)
# Patrones más flexibles para artículos
patron_articulo1 = re.compile(r'^Art[íi]?culo\s+(\d+[\s\w]*?)[\.\s°\-–—]+(.+)$', re.IGNORECASE)
patron_articulo2 = re.compile(r'^Art[\.\s]+(\d+[\s\w]*?)[\.\s°\-–—]+(.+)$', re.IGNORECASE)
patron_articulo3 = re.compile(r'^Art[íi]?culo\s+(\d+[\s\w]*?)$', re.IGNORECASE)  # Solo número
patron_articulo4 = re.compile(r'^Art[\.\s]+(\d+[\s\w]*?)$', re.IGNORECASE)  # Solo número versión corta
patron_inciso = re.compile(r'^([a-z])\)\s+(.+)$', re.IGNORECASE)

def guardar_articulo():
    global articulo_actual, texto_acumulado
    if articulo_actual:
        if texto_acumulado.strip():
            if not articulo_actual.get('texto'):
                articulo_actual['texto'] = texto_acumulado.strip()
            else:
                articulo_actual['texto'] += " " + texto_acumulado.strip()
        texto_acumulado = ""

def agregar_articulo(articulo):
    global titulo_actual, capitulo_actual
    if capitulo_actual:
        capitulo_actual["articulos"].append(articulo)
    elif titulo_actual:
        titulo_actual["articulos"].append(articulo)
    else:
        # Crear título inicial si no existe
        if not ley["ley"]["titulos"]:
            ley["ley"]["titulos"].append({
                "numero": "0",
                "nombre": "Disposiciones Iniciales",
                "capitulos": [],
                "articulos": []
            })
            titulo_actual = ley["ley"]["titulos"][0]
        ley["ley"]["titulos"][0]["articulos"].append(articulo)

# Procesar líneas
i = 0
while i < len(lineas):
    linea = lineas[i].strip()
    
    if not linea:
        i += 1
        continue
    
    # Detectar TITULO
    match_titulo = patron_titulo.match(linea)
    if match_titulo:
        guardar_articulo()
        numero_titulo = match_titulo.group(1)
        
        # Buscar nombre del título en líneas siguientes
        i += 1
        nombre_titulo = ""
        while i < len(lineas):
            siguiente = lineas[i].strip()
            if not siguiente:
                i += 1
                continue
            if (patron_articulo1.match(siguiente) or patron_articulo2.match(siguiente) or 
                patron_articulo3.match(siguiente) or patron_articulo4.match(siguiente) or
                patron_capitulo.match(siguiente) or patron_titulo.match(siguiente)):
                break
            nombre_titulo += " " + siguiente
            i += 1
        
        titulo_actual = {
            "numero": numero_titulo,
            "nombre": nombre_titulo.strip(),
            "capitulos": [],
            "articulos": []
        }
        ley["ley"]["titulos"].append(titulo_actual)
        capitulo_actual = None
        articulo_actual = None
        continue
    
    # Detectar CAPITULO
    match_capitulo = patron_capitulo.match(linea)
    if match_capitulo:
        guardar_articulo()
        numero_capitulo = match_capitulo.group(1)
        
        # Buscar nombre del capítulo
        i += 1
        nombre_capitulo = ""
        while i < len(lineas):
            siguiente = lineas[i].strip()
            if not siguiente:
                i += 1
                continue
            if (patron_articulo1.match(siguiente) or patron_articulo2.match(siguiente) or
                patron_articulo3.match(siguiente) or patron_articulo4.match(siguiente) or
                patron_titulo.match(siguiente) or patron_capitulo.match(siguiente)):
                break
            nombre_capitulo += " " + siguiente
            i += 1
        
        capitulo_actual = {
            "numero": numero_capitulo,
            "nombre": nombre_capitulo.strip(),
            "articulos": []
        }
        if titulo_actual:
            titulo_actual["capitulos"].append(capitulo_actual)
        articulo_actual = None
        continue
    
    # Detectar Artículo (varios patrones)
    match_articulo = (patron_articulo1.match(linea) or patron_articulo2.match(linea) or
                     patron_articulo3.match(linea) or patron_articulo4.match(linea))
    
    if match_articulo:
        guardar_articulo()
        
        numero_art = match_articulo.group(1).strip()
        
        # Obtener título del artículo
        if match_articulo.lastindex >= 2:
            titulo_art = match_articulo.group(2).strip()
        else:
            # Buscar título en la siguiente línea
            i += 1
            if i < len(lineas):
                titulo_art = lineas[i].strip()
            else:
                titulo_art = ""
        
        articulo_actual = {
            "numero": numero_art,
            "titulo": titulo_art,
            "texto": ""
        }
        
        agregar_articulo(articulo_actual)
        texto_acumulado = ""
        i += 1
        continue
    
    # Detectar incisos
    match_inciso = patron_inciso.match(linea)
    if match_inciso and articulo_actual:
        letra = match_inciso.group(1).lower()
        texto_inciso = match_inciso.group(2).strip()
        
        # Guardar texto previo del artículo
        if texto_acumulado.strip() and not articulo_actual.get('texto'):
            articulo_actual['texto'] = texto_acumulado.strip()
            texto_acumulado = ""
        
        if 'incisos' not in articulo_actual:
            articulo_actual['incisos'] = []
        
        articulo_actual["incisos"].append({
            "letra": letra,
            "texto": texto_inciso
        })
        i += 1
        continue
    
    # Acumular texto del artículo o inciso
    if articulo_actual:
        # Si hay incisos y el texto no parece ser un nuevo elemento, agregarlo al último inciso
        if 'incisos' in articulo_actual and articulo_actual['incisos'] and not match_inciso:
            # Verificar si no es inicio de nuevo artículo o sección
            if not (patron_articulo1.match(linea) or patron_articulo2.match(linea) or
                   patron_titulo.match(linea) or patron_capitulo.match(linea)):
                articulo_actual['incisos'][-1]['texto'] += " " + linea
        else:
            texto_acumulado += " " + linea
    
    i += 1

# Guardar último artículo
guardar_articulo()

# Limpiar estructura
def limpiar_estructura(obj):
    if isinstance(obj, dict):
        # Eliminar arrays vacíos
        if 'incisos' in obj and not obj['incisos']:
            del obj['incisos']
        if 'capitulos' in obj and not obj['capitulos']:
            del obj['capitulos']
        
        # Limpiar espacios extras en textos
        for key in ['texto', 'titulo', 'nombre']:
            if key in obj and isinstance(obj[key], str):
                obj[key] = re.sub(r'\s+', ' ', obj[key]).strip()
        
        for value in obj.values():
            limpiar_estructura(value)
    elif isinstance(obj, list):
        for item in obj:
            limpiar_estructura(item)

limpiar_estructura(ley)

# Guardar JSON
with open('ley_contrato_trabajo_completa.json', 'w', encoding='utf-8') as f:
    json.dump(ley, f, ensure_ascii=False, indent=2)

# Estadísticas
print("=" * 60)
print("JSON generado: ley_contrato_trabajo_completa.json")
print("=" * 60)
print(f"Total de titulos: {len(ley['ley']['titulos'])}")

total_articulos = 0
total_capitulos = 0
total_incisos = 0

for titulo in ley['ley']['titulos']:
    total_articulos += len(titulo.get('articulos', []))
    total_capitulos += len(titulo.get('capitulos', []))
    
    for art in titulo.get('articulos', []):
        total_incisos += len(art.get('incisos', []))
    
    for cap in titulo.get('capitulos', []):
        total_articulos += len(cap.get('articulos', []))
        for art in cap.get('articulos', []):
            total_incisos += len(art.get('incisos', []))

print(f"Total de capitulos: {total_capitulos}")
print(f"Total de articulos: {total_articulos}")
print(f"Total de incisos: {total_incisos}")
print("=" * 60)
print("Proceso completado exitosamente")

