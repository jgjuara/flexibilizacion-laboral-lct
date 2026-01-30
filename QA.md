# Quality Assurance Workflow

This project includes a QA script to verify the integrity of the published static site (`docs/`).

## Verification Scope

The script `utils/qa_site.py` performs the following checks:

1.  **Static Assets:** Verifies the existence of core files (`index.html`, `app.js`, `styles.css`).
2.  **Data Consistency:** 
    - Parses `index.html` to find all referenced Laws (via `<option>` values).
    - Verifies that a corresponding `comparacion_global_ley_{NUMBER}.json` exists in `docs/data/`.
3.  **Data Validity:**
    - Validates that every referenced JSON file is valid JSON.
    - Checks for essential schema keys (`ley`, `ley.titulos`).
4.  **Cleanliness:**
    - Warns if there are orphaned JSON files in `docs/data/` that are not referenced in the UI.

## Execution

Run the QA script using `uv`:

```bash
uv run utils/qa_site.py
```

## Exit Codes

- `0`: Success. All checks passed.
- `1`: Failure. Critical missing files or invalid data found.

## Maintenance

Run this script before deploying or publishing changes to the `docs/` folder.
