#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para extraer todas las leyes modificadas por el dictamen.
Analiza todos los archivos JSON del dictamen y extrae menciones de leyes
tanto del encabezado como del texto de las operaciones.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Optional

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
}

# Patrones de texto que indican que se está hablando de la LCT
PATRONES_LCT = [
    re.compile(r"ley\s+de\s+contrato\s+de\s+trabajo", re.IGNORECASE),
    re.compile(r"art[íi]culo\s+\d+.*de\s+la\s+ley", re.IGNORECASE),  # "artículo X de la ley"
    re.compile(r"sustit[úu]yese.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
    re.compile(r"modif[íi]case.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
    re.compile(r"incorp[óo]rase.*art[íi]culo.*de\s+la\s+ley", re.IGNORECASE),
]

# Patrones para extraer números de ley
PATRONES_LEY = [
    # "Ley N° 20744"
    re.compile(r"ley\s+n[°º]\s*([0-9\.\-]+)", re.IGNORECASE),
    # "Ley 20744"
    re.compile(r"ley\s+([0-9\.\-]+)", re.IGNORECASE),
    # "Ley 20.744"
    re.compile(r"ley\s+([0-9]{1,2}\.[0-9]{3,5})", re.IGNORECASE),
    # "Ley 12.908"
    re.compile(r"ley\s+([0-9]{2}\.[0-9]{3,5})", re.IGNORECASE),
    # "Decreto Ley 13.839/46"
    re.compile(r"decreto\s+ley\s+([0-9\.]+)", re.IGNORECASE),
    # "Decreto-Ley 17.250/67"
    re.compile(r"decreto[\s-]ley\s+([0-9\.]+)", re.IGNORECASE),
]


def extraer_numeros_ley(texto: str, contexto_titulo: Optional[str] = None) -> Set[str]:
    """
    Extrae todos los números de ley mencionados en un texto.
    Retorna un set con los números encontrados (normalizados).
    
    Args:
        texto: Texto a analizar
        contexto_titulo: Número de título del dictamen (para inferir leyes por contexto)
    """
    numeros = set()
    
    if not texto:
        return numeros
    
    # Buscar patrones de números de ley
    for patron in PATRONES_LEY:
        matches = patron.findall(texto)
        for match in matches:
            # Normalizar: quitar puntos y espacios, mantener solo números y guiones
            normalizado = match.replace(".", "").replace(" ", "").strip()
            if normalizado:
                numeros.add(normalizado)
    
    # Buscar nombres comunes de leyes
    texto_lower = texto.lower()
    for nombre, numero in LEY_NOMBRES_A_NUMEROS.items():
        if nombre in texto_lower:
            numeros.add(numero)
    
    # Detectar menciones implícitas de LCT
    # Si el encabezado menciona "artículo X de la ley" sin número, probablemente es LCT
    for patron_lct in PATRONES_LCT:
        if patron_lct.search(texto):
            numeros.add("20744")
            break
    
    # Si el título es I y menciona "de la ley" o "esta ley" sin número específico,
    # es muy probable que sea LCT (20744)
    if contexto_titulo == "I":
        if re.search(r"(?:de\s+la\s+ley|esta\s+ley)", texto_lower):
            # Verificar que no haya otra ley mencionada explícitamente
            tiene_ley_explicita = any(patron.search(texto) for patron in PATRONES_LEY)
            if not tiene_ley_explicita:
                numeros.add("20744")
    
    return numeros


def analizar_operacion(operacion: Dict, contexto_titulo: Optional[str] = None) -> Set[str]:
    """
    Analiza una operación y extrae todas las leyes mencionadas.
    
    Args:
        operacion: Diccionario con la operación
        contexto_titulo: Número de título para inferir leyes por contexto
    """
    leyes = set()
    
    # Buscar en el encabezado
    encabezado = operacion.get("encabezado", "")
    if encabezado:
        leyes.update(extraer_numeros_ley(encabezado, contexto_titulo))
    
    # Buscar en el texto nuevo
    texto_nuevo = operacion.get("texto_nuevo", "")
    if texto_nuevo:
        leyes.update(extraer_numeros_ley(texto_nuevo, contexto_titulo))
    
    # Si ya tiene ley_numero, agregarlo
    ley_numero = operacion.get("ley_numero")
    if ley_numero:
        # Normalizar
        normalizado = str(ley_numero).replace(".", "").replace(" ", "").strip()
        if normalizado:
            leyes.add(normalizado)
    
    return leyes


def analizar_titulo(archivo: Path) -> Dict[str, any]:
    """
    Analiza un archivo JSON de título y extrae todas las leyes mencionadas.
    """
    with open(archivo, "r", encoding="utf-8") as f:
        operaciones = json.load(f)
    
    leyes_por_operacion = []
    todas_las_leyes = set()
    
    # Extraer número de título del nombre del archivo
    titulo_num = archivo.stem.replace("dictamen_modernizacion_laboral_titulo_", "")
    
    for op in operaciones:
        leyes_op = analizar_operacion(op, contexto_titulo=titulo_num)
        todas_las_leyes.update(leyes_op)
        
        leyes_por_operacion.append({
            "dictamen_articulo": op.get("dictamen_articulo"),
            "encabezado": op.get("encabezado", "")[:100] + "..." if len(op.get("encabezado", "")) > 100 else op.get("encabezado", ""),
            "leyes_encontradas": sorted(list(leyes_op)),
            "ley_numero_original": op.get("ley_numero"),
        })
    
    return {
        "titulo": titulo_num,
        "total_operaciones": len(operaciones),
        "leyes_unicas": sorted(list(todas_las_leyes)),
        "operaciones_con_leyes": leyes_por_operacion,
    }


def main():
    """
    Analiza todos los archivos del dictamen y genera un reporte de leyes modificadas.
    """
    data_dir = Path("data")
    
    # Encontrar todos los archivos de títulos
    archivos_titulos = sorted(data_dir.glob("dictamen_modernizacion_laboral_titulo_*.json"))
    
    if not archivos_titulos:
        print("No se encontraron archivos de títulos en data/")
        return
    
    print(f"Analizando {len(archivos_titulos)} archivos de títulos...\n")
    
    resultados_por_titulo = {}
    todas_las_leyes_global = set()
    
    for archivo in archivos_titulos:
        resultado = analizar_titulo(archivo)
        resultados_por_titulo[resultado["titulo"]] = resultado
        todas_las_leyes_global.update(resultado["leyes_unicas"])
    
    # Generar reporte
    print("=" * 80)
    print("REPORTE DE LEYES MODIFICADAS POR EL DICTAMEN")
    print("=" * 80)
    print(f"\nTotal de leyes únicas encontradas: {len(todas_las_leyes_global)}")
    print(f"Leyes: {', '.join(sorted(todas_las_leyes_global))}")
    print("\n" + "=" * 80)
    print("\nDETALLE POR TÍTULO:\n")
    
    def ordenar_titulo(t: str) -> int:
        """Convierte números romanos a enteros para ordenar."""
        romanos = {
            'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
            'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
            'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
            'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
            'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25, 'XXVI': 26
        }
        return romanos.get(t.upper(), 999)
    
    for titulo_num in sorted(resultados_por_titulo.keys(), key=ordenar_titulo):
        resultado = resultados_por_titulo[titulo_num]
        print(f"\nTÍTULO {titulo_num}:")
        print(f"  Operaciones: {resultado['total_operaciones']}")
        print(f"  Leyes encontradas: {', '.join(resultado['leyes_unicas']) if resultado['leyes_unicas'] else 'NINGUNA'}")
        
        # Contar operaciones sin ley identificada
        sin_ley = sum(1 for op in resultado['operaciones_con_leyes'] if not op['leyes_encontradas'])
        if sin_ley > 0:
            print(f"  [ADVERTENCIA] Operaciones sin ley identificada: {sin_ley}")
    
    # Guardar resultados en JSON
    output_file = Path("leyes_modificadas_dictamen.json")
    output_data = {
        "leyes_unicas_globales": sorted(list(todas_las_leyes_global)),
        "resumen_por_titulo": {
            titulo: {
                "total_operaciones": r["total_operaciones"],
                "leyes_unicas": r["leyes_unicas"],
            }
            for titulo, r in resultados_por_titulo.items()
        },
        "detalle_por_titulo": resultados_por_titulo,
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n\nReporte completo guardado en: {output_file}")


if __name__ == "__main__":
    main()

