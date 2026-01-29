# LCT & Herramientas de Análisis Legislativo

Este proyecto proporciona un conjunto de herramientas para procesar, consultar y comparar el texto de **dictámenes legislativos** (como proyectos de reforma o modernización) contra **cada una de las leyes que modifican o afectan**. Si bien se centra fuertemente en la Ley de Contrato de Trabajo (LCT), el sistema está diseñado para identificar y analizar cambios en cualquier norma del ordenamiento jurídico argentino presente en SAIJ.

## Descripción General

El objetivo principal es automatizar la detección de impacto legislativo, permitiendo ver qué artículos de qué leyes están siendo sustituidos, incorporados o derogados por un dictamen específico.

El sistema se compone de varios módulos:
1.  **Scraper (saij-data):** Descarga leyes y metadatos desde el Sistema Argentino de Información Jurídica (SAIJ).
2.  **Parsers:** Normalizan la información de entrada (JSON de SAIJ o PDF de dictámenes) a formatos estructurados comunes.
3.  **Extractor de Leyes:** Identifica automáticamente qué leyes son mencionadas y modificadas dentro de un dictamen.
4.  **Matcher/Comparador:** Vincula las modificaciones propuestas con los artículos vigentes de las leyes afectadas.
5.  **Web UI (docs):** Visualización comparativa lado a lado entre el texto vigente y la propuesta de reforma.

## Estructura del Proyecto

```text
.
├── batch_scraper.py    # Descarga masiva de leyes afectadas
├── matcher/            # Lógica de vinculación (Ley vs Dictamen)
├── parsers/
│   ├── dictamen/       # Extracción de operaciones desde PDFs de dictámenes
│   └── saij/           # Normalización de JSONs oficiales de SAIJ
├── saij-data/          # Módulo core de scraping
├── docs/               # Interfaz web de visualización comparativa
├── data/               # Repositorio de leyes (JSON) y resultados de comparación
└── utils/              # Scripts para detectar inconsistencias y extraer leyes modificadas
```

## Tecnologías Clave

*   **Lenguaje:** Python >= 3.10
*   **Gestión de Dependencias:** `uv`
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
*   **Librerías Python:**
    *   `requests`, `beautifulsoup4` (Scraping)
    *   `pdfplumber` / `pymupdf` (PDF Parsing)
    *   `lxml` (Procesamiento XML/HTML)

## Uso y Ejecución

El proyecto utiliza `uv` para la gestión de entornos y ejecución de scripts.

### 1. Instalación

Sincronizar dependencias:

```bash
uv sync
# Para soporte de PDF (necesario para parser de dictamen):
uv sync --extra pdf
```

### 2. Descarga de Datos (Scraper)

Para descargar un lote de leyes relacionadas con el trabajo:

```bash
uv run batch_scraper.py
```

Esto poblará el directorio `data/` con archivos JSON crudos de SAIJ.

### 3. Procesamiento y Análisis

**Identificar leyes modificadas en un dictamen:**
Analiza los archivos del dictamen para listar todas las leyes afectadas.
```bash
uv run utils/extraer_leyes_modificadas.py
```

**Normalizar una Ley de SAIJ:**
```bash
uv run parsers/saij/parser.py data/20744-lct.json -o data/ley_20744_estructurada.json
```

**Comparar Ley vs Dictamen:**
Genera un JSON con la comparación detallada (sustituciones, derogaciones, incorporaciones).
```bash
uv run utils/comparar_ley_dictamen.py data/ley_20744_estructurada.json data/dictamen_titulo_I.json data/comparacion_20744.json
```

### 4. Visualización Web

La interfaz web se encuentra en la carpeta `docs/`. Es una aplicación estática (SPA).
Para visualizarla, simplemente sirve la carpeta `docs/` con cualquier servidor HTTP estático, o abre el `index.html` (aunque algunos navegadores pueden bloquear la carga de JSON locales por CORS).

```bash
# Ejemplo con python
cd docs
python -m http.server
```

## Convenciones de Desarrollo

*   **Gestor de Paquetes:** Estrictamente `uv`. No usar `pip` directamente.
*   **Estructura de Datos:** Los JSONs de salida siguen esquemas específicos (ver `schema_ley_template.json` o ejemplos en `data/`).
*   **Rutas:** Los scripts asumen que se ejecutan desde la raíz del proyecto o manejan rutas relativas a la raíz. Los datos siempre van a `data/`.
