#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para consultar artículos de la Ley de Contrato de Trabajo
Uso: python consultar_ley.py [numero_articulo]
"""

import json
import sys
import io

# Configurar encoding UTF-8 para salida en Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def cargar_ley():
    """Carga el JSON de la ley"""
    with open('ley_contrato_trabajo_completa.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def buscar_articulo(data, numero):
    """Busca un artículo por su número"""
    for titulo in data['ley']['titulos']:
        # Buscar en artículos directos del título
        for art in titulo.get('articulos', []):
            if art['numero'] == str(numero):
                return art, titulo
        
        # Buscar en artículos de capítulos
        for cap in titulo.get('capitulos', []):
            for art in cap.get('articulos', []):
                if art['numero'] == str(numero):
                    return art, titulo
    
    return None, None

def mostrar_articulo(articulo, titulo):
    """Muestra un artículo formateado"""
    print("=" * 70)
    print(f"ARTÍCULO {articulo['numero']}")
    print("=" * 70)
    print(f"Título: {articulo['titulo']}")
    print(f"Pertenece a: Título {titulo['numero']} - {titulo['nombre']}")
    print("-" * 70)
    print(f"\nTexto:\n{articulo['texto']}")
    
    if 'incisos' in articulo and articulo['incisos']:
        print("\n" + "-" * 70)
        print("Incisos:")
        for inciso in articulo['incisos']:
            print(f"\n  {inciso['letra']}) {inciso['texto']}")
    
    print("\n" + "=" * 70)

def listar_articulos(data):
    """Lista todos los artículos disponibles"""
    print("=" * 70)
    print("ÍNDICE DE ARTÍCULOS - LEY DE CONTRATO DE TRABAJO")
    print("=" * 70)
    
    for titulo in data['ley']['titulos']:
        print(f"\n{titulo['numero']}. {titulo['nombre']}")
        print("-" * 70)
        
        # Artículos directos
        for art in titulo.get('articulos', []):
            print(f"  Art. {art['numero']:>4} - {art['titulo'][:50]}")
        
        # Artículos en capítulos
        for cap in titulo.get('capitulos', []):
            print(f"\n  Capítulo {cap['numero']}: {cap['nombre']}")
            for art in cap.get('articulos', []):
                print(f"    Art. {art['numero']:>4} - {art['titulo'][:45]}")

def main():
    data = cargar_ley()
    
    if len(sys.argv) > 1:
        # Buscar artículo específico
        numero = sys.argv[1]
        articulo, titulo = buscar_articulo(data, numero)
        
        if articulo:
            mostrar_articulo(articulo, titulo)
        else:
            print(f"No se encontró el artículo {numero}")
            print("Usa 'python consultar_ley.py' sin argumentos para ver todos los artículos")
    else:
        # Listar todos los artículos
        listar_articulos(data)

if __name__ == '__main__':
    main()

