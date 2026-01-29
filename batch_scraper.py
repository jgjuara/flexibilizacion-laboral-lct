"""
Descarga en lote leyes desde SAIJ usando el scraper del proyecto.

Asume conexión a internet y que SAIJ responde con el JSON esperado.
Garantiza continuar con el resto de las leyes si alguna falla.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from saijdata.scraper import scraper_completo


LEYES = [
    "11544",
    "12713",
    "12867",
    "12908",
    "13839",
    "14250",
    "14546",
    "14786",
    "14954",
    "17250",
    "20657",
    "20744",
    "23079",
    "23472",
    "23546",
    "23551",
    "23759",
    "24013",
    "24156",
    "24241",
    "24467",
    "24493",
    "24714",
    "25212",
    "25674",
    "25877",
    "26590",
    "26727",
    "26844",
    "27423",
    "27553",
    "27555",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga en lote leyes desde SAIJ usando saij-data.",
    )
    parser.add_argument(
        "--directorio",
        type=str,
        default="data",
        help="Directorio destino (por defecto: data).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Segundos de espera entre descargas (por defecto: 1.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No descarga, solo muestra lo que haría.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    destino = Path(args.directorio)
    destino.mkdir(parents=True, exist_ok=True)

    errores: list[str] = []
    for idx, numero in enumerate(LEYES, start=1):
        if args.dry_run:
            print(f"[{idx}/{len(LEYES)}] DRY-RUN: ley {numero} -> {destino}")
            continue

        try:
            print(f"[{idx}/{len(LEYES)}] Descargando ley {numero}...")
            scraper_completo(int(numero), directorio_destino=str(destino))
        except Exception as exc:
            errores.append(f"{numero}: {exc}")

        if idx < len(LEYES):
            time.sleep(args.sleep)

    if errores:
        print("\nErrores:")
        for error in errores:
            print(f"- {error}")
        return 1

    print("\nDescarga completa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
