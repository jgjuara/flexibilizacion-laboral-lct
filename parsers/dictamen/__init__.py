"""Parser para extraer operaciones de dictámenes desde PDF."""

import re
from typing import Dict, Any, List

from .parser import (
    parse_dictamen_pdf,
    parse_dictamen_pdf_legacy,
    DictamenArticulo,
    ObjetivoAccion,
    Operation,  # Mantener para compatibilidad
)

__all__ = [
    "parse_dictamen_pdf",
    "parse_dictamen_pdf_legacy",
    "DictamenArticulo",
    "ObjetivoAccion",
    "Operation",
    "dictamen_articulo_to_legacy_dict",
    "load_dictamen_json",
]


def dictamen_articulo_to_legacy_dict(articulo: DictamenArticulo) -> Dict[str, Any]:
    """
    Convierte un DictamenArticulo al formato legacy (diccionario con campos antiguos).
    Útil para compatibilidad con código existente.
    """
    # Extraer encabezado (primera línea del texto completo)
    encabezado = articulo.texto_completo.split("\n")[0] if articulo.texto_completo else ""
    
    # Extraer texto_nuevo (todo después del encabezado)
    texto_nuevo = None
    if articulo.texto_completo:
        lines = articulo.texto_completo.split("\n")
        if len(lines) > 1:
            # Buscar donde empieza el texto nuevo (después de "por el siguiente:" o similar)
            texto_nuevo_lines = []
            found_trigger = False
            for line in lines[1:]:
                if re.search(r"por\s+el\s+siguiente|el\s+siguiente\s+texto", line, re.IGNORECASE):
                    found_trigger = True
                    after_trigger = line.split(":", 1)[-1].strip()
                    if after_trigger:
                        texto_nuevo_lines.append(after_trigger)
                    continue
                if found_trigger or (line.strip() and not line.strip().startswith("ARTÍCULO")):
                    texto_nuevo_lines.append(line)
            
            if texto_nuevo_lines:
                texto_nuevo = "\n".join(texto_nuevo_lines).strip()
    
    return {
        "dictamen_articulo": articulo.dictamen_articulo,
        "encabezado": encabezado,
        "accion": articulo.objetivo_accion.accion,
        "ley_numero": articulo.objetivo_accion.ley_afectada,
        "destino_articulo": articulo.objetivo_accion.destino_articulo,
        "destino_inciso": articulo.objetivo_accion.destino_inciso,
        "destino_articulo_padre": articulo.objetivo_accion.destino_articulo_padre,
        "destino_capitulo": articulo.objetivo_accion.destino_capitulo,
        "texto_nuevo": texto_nuevo,
        "texto_nuevo_lineas": texto_nuevo.split("\n") if texto_nuevo else None,
    }


def load_dictamen_json(path: str, formato_nuevo: bool = True) -> List[Dict[str, Any]]:
    """
    Carga un JSON de dictamen y retorna lista de diccionarios.
    
    Args:
        path: Ruta al archivo JSON
        formato_nuevo: Si True, espera formato nuevo (DictamenArticulo).
                      Si False, espera formato legacy (Operation).
    
    Returns:
        Lista de diccionarios en formato legacy para compatibilidad
    """
    import json
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        raise ValueError("El JSON debe contener una lista de artículos")
    
    if formato_nuevo:
        # Convertir de formato nuevo a legacy
        result = []
        for item in data:
            # Reconstruir DictamenArticulo desde dict
            objetivo_dict = item.get("objetivo_accion", {})
            objetivo = ObjetivoAccion(
                tipo=objetivo_dict.get("tipo", "modifica"),
                ley_afectada=objetivo_dict.get("ley_afectada"),
                accion=objetivo_dict.get("accion"),
                destino_articulo=objetivo_dict.get("destino_articulo"),
                destino_inciso=objetivo_dict.get("destino_inciso"),
                destino_articulo_padre=objetivo_dict.get("destino_articulo_padre"),
                destino_capitulo=objetivo_dict.get("destino_capitulo"),
                descripcion=objetivo_dict.get("descripcion"),
            )
            articulo = DictamenArticulo(
                dictamen_articulo=item.get("dictamen_articulo", ""),
                titulo=item.get("titulo", ""),
                texto_completo=item.get("texto_completo", ""),
                objetivo_accion=objetivo,
            )
            result.append(dictamen_articulo_to_legacy_dict(articulo))
        return result
    else:
        # Ya está en formato legacy
        return data

