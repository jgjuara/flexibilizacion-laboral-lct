# saij-data

## Project Overview

`saij-data` is a Python-based scraper designed to retrieve semi-structured legislative data from the **Sistema Argentino de Información Jurídica (SAIJ)**. It automates the process of searching for regulations by number, extracting document UUIDs, and downloading the corresponding JSON content containing metadata and full text.

### Key Features
- **Automatic Search:** Finds regulations by their number (e.g., 20744).
- **UUID Extraction:** Parses search results to identify document unique identifiers.
- **JSON Retrieval:** Downloads the full semi-structured JSON representation of the legal document.
- **Smart Naming:** Automatically names output files based on document metadata (number, type, date).

## Tech Stack

- **Language:** Python >= 3.10
- **Package Manager:** [uv](https://github.com/astral-sh/uv)
- **Dependencies:**
  - `requests`: HTTP client.
  - `beautifulsoup4`: HTML parsing (fallback for embedded JSON).
  - `lxml`: XML/HTML parser.

## Building and Running

This project uses `uv` for strict dependency management.

### Installation

1.  **Sync Dependencies:**
    ```bash
    uv sync
    ```

### Usage

Run the scraper using `uv run`. The main entry point is `scraper.py`.

**Basic Usage:**
```bash
uv run scraper.py <NORM_NUMBER>
# Example:
uv run scraper.py 20744
```

**Options:**

- `--directorio <path>`: Specify output directory.
- `--archivo <name>`: Specify custom filename (without extension).
- `--uuid <uuid>`: Bypass search and use a specific document UUID directly.

**Examples:**
```bash
# Save to specific folder
uv run scraper.py 26206 --directorio data

# Custom filename
uv run scraper.py 24449 --archivo "ley-contrato-trabajo"
```

## Architecture

The core logic resides in `scraper.py`:

1.  **`buscar_ley_json(numero_norma)`**:
    - Queries SAIJ search endpoint.
    - Parses response (handling both direct JSON and embedded JSON in HTML).
    - Returns a list of document UUIDs.

2.  **`obtener_json_documento(uuid)`**:
    - Requests the specific document via the `view-document` endpoint.
    - Returns the raw JSON data.

3.  **`scraper_completo`**:
    - Orchestrates the search, extraction, and saving process.

## Development Conventions

- **Dependency Management:** strictly use `uv`.
  - Add packages: `uv add <package>`
  - Run scripts: `uv run <script>`
- **Type Hinting:** Use Python type hints for all functions.
- **Logging:** Use the standard `logging` module for output instead of `print` (except for CLI user feedback).
- **Error Handling:** Raise specific exceptions (`ValueError`, `requests.RequestException`) and handle them gracefully in the main block.
