# LCT - Ley de Contrato de Trabajo

Herramientas para procesar, consultar y comparar la Ley de Contrato de Trabajo con dictámenes de modificación.

## Estructura del Proyecto

El proyecto está organizado en 4 componentes principales:

### 1. Parser de JSON de SAIJ (`parsers/saij/`)
Convierte el JSON oficial de SAIJ a un formato estructurado.

**Uso:**
```bash
uv run parsers/saij/parser.py view-document.json -o data/ley_contrato_trabajo_oficial_completa.json
```

### 2. Parser de PDF Dictamen (`parsers/dictamen/`)
Extrae operaciones legislativas desde PDFs de dictámenes.

**Uso:**
```bash
uv run parsers/dictamen/parser.py "Dictamen.pdf" -o data/dictamen_parseado
```

### 3. Lógica de Matcheo (`matcher/`)
Compara dictámenes con la ley para identificar artículos afectados.

**Uso desde Python:**
```python
from matcher import process_dictamen_data
import json

ley_data = json.load(open('data/ley_contrato_trabajo_oficial_completa.json'))
dictamen_data = json.load(open('data/dictamen_parseado_titulo_I.json'))

result = process_dictamen_data(dictamen_data, ley_data)
print(f"Artículos modificados: {result.modified_articles}")
```

### 4. Interfaz Web (`web/`)
Interfaz de comparación lado a lado entre ley actual y dictamen propuesto.

**Uso:**
Abrir `web/index.html` en un navegador (requiere servidor local para cargar JSONs).

## Instalación

```bash
# Instalar dependencias
uv sync

# Instalar dependencias opcionales para PDF
uv sync --extra pdf
```

## Requisitos

- Python 3.8+
- uv (gestor de paquetes)
- Para procesar PDFs: `pdfplumber` o `pymupdf`

## Datos

Los archivos JSON generados y de entrada deben estar en la carpeta `data/`.
