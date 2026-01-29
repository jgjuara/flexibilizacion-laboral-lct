"""
Detecta inconsistencias entre texto_completo y objetivo_accion en dictamen_parseado.json

Busca menciones de leyes en texto_completo que no coincidan con ley_afectada.
"""

import json
import re
from pathlib import Path


def extraer_leyes_mencionadas(texto: str) -> list[str]:
    """
    Extrae números de leyes mencionadas en el texto.
    
    Busca patrones como:
    - Ley N° 12345
    - Ley Nº 12345
    - Ley 12345
    - ley N° 12345
    - Ley de Contrato de Trabajo N° 20.744
    """
    patrones = [
        # Patrón con N° o Nº (más específico, prioridad alta)
        r'[Ll]ey\s+(?:de\s+\w+(?:\s+de\s+\w+)*\s+)?N[°º]\s*(\d+(?:\.\d+)?)',
        # Patrón sin N° (menos específico)
        r'[Ll]ey\s+(\d{4,5}(?:\.\d{3})?)\b',
    ]
    
    leyes = set()
    for patron in patrones:
        matches = re.finditer(patron, texto)
        for match in matches:
            # Normalizar: remover puntos de miles
            ley = match.group(1).replace('.', '')
            # Solo agregar si parece un número de ley válido (4-5 dígitos)
            if ley.isdigit() and 4 <= len(ley) <= 5:
                leyes.add(ley)
    
    return sorted(leyes)


def detectar_inconsistencias(ruta_json: str) -> list[dict]:
    """
    Detecta inconsistencias entre texto_completo y objetivo_accion.
    
    Returns:
        Lista de diccionarios con información sobre cada inconsistencia
    """
    with open(ruta_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    inconsistencias = []
    
    for idx, item in enumerate(data):
        dictamen_articulo = item.get('dictamen_articulo', 'N/A')
        titulo = item.get('titulo', 'N/A')
        texto_completo = item.get('texto_completo', '')
        objetivo = item.get('objetivo_accion', {})
        
        ley_afectada = objetivo.get('ley_afectada')
        
        # Extraer leyes mencionadas en el texto
        leyes_en_texto = extraer_leyes_mencionadas(texto_completo)
        
        # Verificar inconsistencias
        if ley_afectada:
            ley_afectada_str = str(ley_afectada)
            
            # Ignorar marcadores especiales
            if ley_afectada_str in ['IMPUESTO_GANANCIAS']:
                continue
            
            # Verificar si la ley afectada está en el texto (con o sin punto)
            # Por ejemplo, 18345 puede aparecer como "18.345" en el texto
            ley_con_punto = ley_afectada_str[:2] + "." + ley_afectada_str[2:] if len(ley_afectada_str) == 5 else ley_afectada_str
            ley_en_texto = ley_afectada_str in texto_completo or ley_con_punto in texto_completo
            
            # Si la ley afectada no está en el texto, es sospechoso
            if not ley_en_texto and ley_afectada_str not in leyes_en_texto and leyes_en_texto:
                # Verificar si es un falso positivo: el texto puede contener múltiples artículos
                # Si el texto menciona "ARTÍCULO XXX-" múltiples veces, puede ser que las otras
                # leyes estén en artículos posteriores concatenados
                num_articulos = texto_completo.count('ARTÍCULO')
                
                # Si hay múltiples artículos en el texto, es probable un falso positivo
                if num_articulos <= 2:  # Solo reportar si hay 2 o menos artículos
                    inconsistencias.append({
                        'indice': idx,
                        'dictamen_articulo': dictamen_articulo,
                        'titulo': titulo,
                        'ley_afectada_declarada': ley_afectada_str,
                        'leyes_en_texto': leyes_en_texto,
                        'tipo': 'ley_afectada_no_mencionada',
                        'descripcion': f'La ley {ley_afectada_str} no aparece en el texto, pero se mencionan: {", ".join(leyes_en_texto)}'
                    })
        
        # Si hay leyes en el texto pero ley_afectada es null
        elif leyes_en_texto and objetivo.get('tipo') == 'modifica':
            inconsistencias.append({
                'indice': idx,
                'dictamen_articulo': dictamen_articulo,
                'titulo': titulo,
                'ley_afectada_declarada': None,
                'leyes_en_texto': leyes_en_texto,
                'tipo': 'ley_afectada_null',
                'descripcion': f'ley_afectada es null pero se mencionan leyes: {", ".join(leyes_en_texto)}'
            })
    
    return inconsistencias


def main():
    ruta = Path(__file__).parent.parent / 'dictamen_parseado.json'
    
    print("Analizando dictamen_parseado.json...\n")
    inconsistencias = detectar_inconsistencias(str(ruta))
    
    if not inconsistencias:
        print("OK - No se detectaron inconsistencias")
        return
    
    print(f"Se detectaron {len(inconsistencias)} inconsistencias:\n")
    print("=" * 80)
    
    for inc in inconsistencias:
        print(f"\nArticulo {inc['dictamen_articulo']} (Titulo {inc['titulo']}) - Indice: {inc['indice']}")
        print(f"Tipo: {inc['tipo']}")
        print(f"Ley afectada declarada: {inc['ley_afectada_declarada']}")
        print(f"Leyes mencionadas en texto: {', '.join(inc['leyes_en_texto'])}")
        print(f"Descripcion: {inc['descripcion']}")
        print("-" * 80)
    
    # Guardar reporte
    ruta_reporte = Path(__file__).parent.parent / 'reporte_inconsistencias.json'
    with open(ruta_reporte, 'w', encoding='utf-8') as f:
        json.dump(inconsistencias, f, indent=2, ensure_ascii=False)
    
    print(f"\nOK - Reporte guardado en: {ruta_reporte}")


if __name__ == '__main__':
    main()

