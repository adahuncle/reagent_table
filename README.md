# Reagent Table Pipeline

This project builds a reagent/compound dataset from PubChem, stores it in SQLite, and exports template-driven Excel reports with structure images and selected properties.

## What This Project Does

- Resolves compound names to PubChem CID values.
- Accepts either compound names or direct CID inputs during ingestion.
- Pulls compound metadata, computed properties, experimental properties, and hazard/use text from PubChem APIs.
- Uses HTTP retries with request timeouts for more resilient PubChem API calls.
- Stores data in a local SQLite database (`compounds.db`) in both long and wide formats.
- Downloads 2D structure images into `structure_images/`.
- Exports report-style Excel tables (`compound_report.xlsx`) based on JSON templates in `templates/`.
- Cleans up temporary image artifacts created during Excel export.
- Includes helper scripts for DB inspection and one-off analysis.

## Current Workflow

1. Ingest compounds from PubChem:
   - Script: `query_pubchem.py`
   - Input: comma-separated compound names or CIDs
   - Output: updates `compounds.db`, writes `structure_images/*.png`, rebuilds `compound_properties_wide` once after batch ingestion

2. Export Excel report:
   - Preferred script: `export_excel.py`
   - Input: `compounds.db` and template JSON
   - Output: `compound_report.xlsx`

3. (Optional) Build new template interactively:
   - Script: `generate_template_cli.py`
   - Output: new `templates/<name>.json`

## Repository Layout

- `query_pubchem.py`: main ingestion + normalization + DB write path
- `export_excel.py`: stable Excel export path (full dataset)
- `excel.py`: alternate exporter (full dataset by default, optional sampling via `EXCEL_SAMPLE_SIZE`)
- `generate_template_cli.py`: interactive template generator
- `rubber_additive_report_with_pubchem.py`: specialized export for specific additive targets
- `pinnacle_test.py`: raw PubChem JSON dump utility for debugging API payloads
- `ml.py`: experimental hazard-classification script
- `test.py`, `tester.py`, `test_long.py`: DB inspection/profiling scripts (not automated tests)
- `templates/*.json`: output layout definitions
- `structure_images/`: downloaded structure images
- `_extracted_reagent_table/`: currently empty output folder
- `common_reagents_500.csv`: reagent seed list
- `compounds.db`: local working database artifact
- `compound_report.xlsx`: generated report artifact
- `requirements.txt`: Python dependency manifest
- `.gitignore`: ignores generated/runtime artifacts

## Setup

Recommended Python version: 3.11+

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### 1) Ingest compounds into SQLite

```bash
python query_pubchem.py
```

When prompted, enter one or more names:

```text
acetic acid, sulfuric acid, benzene
```

CID input is also supported:

```text
702, 1118
```

### 2) Generate Excel from a template

```bash
python export_excel.py
```

The script prompts for a template in `templates/` and writes `compound_report.xlsx`.

### 3) Create a new template

```bash
python generate_template_cli.py
```

### 4) Optional sampled export from `excel.py`

`excel.py` exports all rows by default. To sample during testing:

```bash
set EXCEL_SAMPLE_SIZE=5
python excel.py
```

## Template Model

Templates define report columns and rendering types:

- `text`: direct field output
- `image`: embedded image from a path field
- `composite`: combines image and/or text components in one column
- `blank`: spacer column
- `computed`: calls built-in formatting helpers (example: hazard summary)

Core field groups used by most templates:

- `core`: fields from `compounds`
- `properties`: fields from `compound_properties_wide`

## Data Model (SQLite)

- `compounds`: one row per CID with core identifiers and image path
- `properties`: normalized long table of property pairs by category
- `compound_properties_wide`: pivoted one-row-per-CID wide table used by exporters

## Development Record

Baseline snapshot date: 2026-03-11

### Current State Summary

- Main ingestion logic is centralized in `query_pubchem.py`.
- Ingestion now supports direct CID input and uses retries/timeouts for HTTP calls.
- Wide-table regeneration now runs once after batch ingestion in CLI flows.
- Excel exporters now clean temporary composite image files.
- Excel exporting still exists in two similar scripts (`export_excel.py` and `excel.py`).
- Several scripts are exploratory/diagnostic and appear to be retained for analysis.
- Generated artifacts (`compounds.db`, `compound_report.xlsx`, `structure_images/`, `__pycache__/`) are present in workspace.

### Known Technical Debt and Risks

- Duplicate exporter implementations increase maintenance cost.
- No formal test suite (`pytest`/`unittest`) is present.
- No lockfile with exact pinned versions is present (`requirements.txt` currently uses minimum versions).

### Suggested Cleanup Roadmap

Priority 0 (correctness + safety):
- Consolidate to one exporter entrypoint (`export_excel.py`) and mark `excel.py` as test-only or remove.
- Add tests for CID/name resolution, normalization, and export lifecycle behavior.

Priority 1 (structure + maintainability):
- Refactor shared helpers (normalization, wrapping, image composition) into reusable modules.
- Split scripts into package structure, for example:
  - `src/reagent_table/ingest.py`
  - `src/reagent_table/export.py`
  - `src/reagent_table/templates.py`
- Move to `pyproject.toml` and pin/lock exact dependency versions.

Priority 2 (quality + scale):
- Add automated tests for normalization logic, template rendering, and DB schema assumptions.
- Add CLI argument support (no interactive prompts required for batch usage).
- Add logging levels and structured error reporting.

### Change Log Template

Use this section as a living record. Add one entry per meaningful update.

```text
## 2026-03-11
- Change: Fixed CID-force ingestion path, repaired normalization numeric extraction, added HTTP retries/timeouts, optimized wide-table rebuild timing, cleaned temp export images, added `.gitignore` + `requirements.txt`.
- Why: Improve correctness, resilience, and day-to-day maintainability.
- Files touched: query_pubchem.py, rubber_additive_report_with_pubchem.py, export_excel.py, excel.py, tester.py, .gitignore, requirements.txt, README.md.
- Validation performed: Python syntax compilation.
- Follow-up actions: Add automated tests and consolidate exporter duplication.

## YYYY-MM-DD
- Change:
- Why:
- Files touched:
- Validation performed:
- Follow-up actions:
```

## Notes for Future Contributors

- Treat `query_pubchem.py` and `export_excel.py` as the default production path.
- Keep templates backward-compatible where possible to avoid breaking exports.
- For any schema changes, update both DB-building logic and template assumptions in the same commit.
- Prefer adding targeted tests before modifying normalization/parsing behavior.
