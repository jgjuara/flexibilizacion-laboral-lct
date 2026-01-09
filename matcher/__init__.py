"""Lógica de matcheo entre dictámenes y leyes."""

from .matcher import (
    get_destino_articulo,
    find_articles_in_chapter,
    process_dictamen_data,
    get_cambio_for_articulo,
    get_incorporated_articles,
    get_all_articles,
    MatchResult,
)

__all__ = [
    "get_destino_articulo",
    "find_articles_in_chapter",
    "process_dictamen_data",
    "get_cambio_for_articulo",
    "get_incorporated_articles",
    "get_all_articles",
    "MatchResult",
]

