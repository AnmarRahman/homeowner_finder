# Homeowner Data Collector (MVP)

This project is a **Python CLI** for collecting and normalizing **county property data** into CSV/JSON/SQLite.

It is designed for the practical, free workflow:

1. start with **one supported county/source**,
2. fetch public parcel/property records,
3. normalize them into one schema,
4. export the results.

## What is included

- A clean adapter-based scraper/fetcher architecture
- A working **mock source** so you can test the full pipeline immediately
- A **Los Angeles County open-data adapter scaffold** that fetches records from a configurable JSON endpoint
- CSV + JSON export
- Optional SQLite persistence
- Basic tests

## Important limitation

There is **no single free statewide homeowner API for California**. California property data is administered at the county level, and Los Angeles County publishes parcel/open-data resources and a property-search portal rather than a statewide homeowner list. The Assessor portal also points users to the Registrar-Recorder/County Clerk for ownership information requests, which means not every public dataset will include owner names directly. citeturn407791search1turn407791search2turn407791search11

Because of that, this MVP is built as a **county adapter system**. You can add more county adapters over time.

## Current source options

### 1. `mock`
Fully working sample data source for testing the pipeline.

### 2. `la_open_data`
Configurable Los Angeles County open-data adapter.

What it does:
- calls a public JSON endpoint you configure,
- normalizes records into one schema,
- exports the results.

What you need to do:
- inspect the exact LA County dataset you want,
- set the endpoint URL and field mappings in `.env`.

This is intentional so the project does not hallucinate undocumented field names.

### 3. `or_deschutes_taxlots`
Deschutes County, Oregon taxlots adapter using the official ArcGIS FeatureServer + related assessor tables.

What it does:
- pulls base taxlot IDs,
- fetches related owner, mailing, assessor address, property class, and value tables,
- normalizes to the shared schema.

### 4. `ca_humboldt_parcels`
Humboldt County, California parcels (owners) adapter using the official county ArcGIS service.

What it does:
- fetches owner name, situs address, mailing address, APN, occupancy flag, and value components,
- normalizes into the shared schema.

## Normalized schema

Every source should return rows shaped like:

- `owner_name`
- `property_address`
- `mailing_address`
- `city`
- `state`
- `zip`
- `parcel_id`
- `property_type`
- `source_url`
- `raw`

## Project layout

```text
homeowner_finder_ca/
  scraper/
    __init__.py
    cli.py
    config.py
    models.py
    normalizer.py
    exporters.py
    storage.py
    sources/
      __init__.py
      base.py
      mock_source.py
      la_open_data.py
      ca_humboldt_parcels.py
      or_deschutes_taxlots.py
      registry.py
  tests/
    test_normalizer.py
    test_exporters.py
    test_registry.py
  data/
  .env.example
  requirements.txt
  README.md
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Copy environment file

```bash
cp .env.example .env
```

## Desktop app (GUI)

Run the app:

```bash
python run_gui.py
```

The app lets you:
- choose state(s),
- choose source(s),
- set limits and filters,
- choose output folder/file/format,
- click `Start` and watch progress in real time.

Use the `Help` button in the app for a quick usage guide.

### Self-update for `.exe`

The packaged app can check for updates on startup and update itself.

Default manifest URL is built in:

- `https://trustbridge-manifest.vercel.app/latest.json`

You can optionally override it with `update_config.json` next to `TrustBridgeLeadBuilder.exe`:

```json
{
  "manifest_url": "https://your-domain.example/trust-bridge/latest.json"
}
```

3. Host `latest.json` like this:

```json
{
  "version": "1.0.1",
  "url": "https://your-domain.example/trust-bridge/TrustBridgeLeadBuilder.exe",
  "sha256": "optional_sha256_here",
  "notes": "Bug fixes and improvements."
}
```

Notes:
- The app compares remote `version` against built-in app version.
- If newer, it prompts user, downloads the new exe, replaces itself, and restarts.
- You still publish a new `.exe` for each release, but users can update in-app.

### Build Windows `.exe`

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Built file:
- `dist\TrustBridgeLeadBuilder.exe`

## Quick start with mock data

```bash
python -m scraper.cli search --source mock --limit 25 --format csv --out data/mock_results.csv
```

## Simple run command (CSV output)

Use this for a shorter command that always writes CSV:

```bash
python run_source.py broward_bcpa --limit 25
```

```bash
python run_source.py la_open_data --limit 25
```

By default, output goes to `data/<source>_results.csv` and the path is printed.

## Los Angeles County open-data setup

Los Angeles County has an Assessor Portal and county open-data resources, including parcel/open-data datasets. citeturn407791search2turn407791search3turn407791search4

To use the `la_open_data` source:

1. Pick a real public JSON endpoint for the LA County dataset you want.
2. Put it in `.env` as `LA_DATASET_URL`.
3. Map the endpoint fields in `.env`.
4. Run the collector.

Example `.env` values:

```env
LA_DATASET_URL=https://example.data.lacounty.gov/resource/your-dataset.json
LA_PAGE_SIZE=100
LA_FIELD_OWNER=owner_name
LA_FIELD_PROPERTY_ADDRESS=property_address
LA_FIELD_MAILING_ADDRESS=mailing_address
LA_FIELD_CITY=city
LA_FIELD_STATE=state
LA_FIELD_ZIP=zip
LA_FIELD_PARCEL_ID=parcel_id
LA_FIELD_PROPERTY_TYPE=property_type
```

Then run:

```bash
python -m scraper.cli search --source la_open_data --limit 100 --format csv --out data/la_results.csv
```

Or the shorter command:

```bash
python run_source.py la_open_data --limit 100
```

## Broward County (BCPA) setup

The Broward County source uses the official BCPA ArcGIS parcel layer by default.
If you want to override it, set `BROWARD_DATASET_URL` in `.env`.

Run it with:

```bash
python run_source.py broward_bcpa --limit 100
```

## Oregon Deschutes County setup

The Oregon source uses the official Deschutes County taxlot FeatureServer and related tables by default.
If needed, override `OR_DESCHUTES_DATASET_URL` and `OR_DESCHUTES_RELATED_URL` in `.env`.

Run it with:

```bash
python run_source.py or_deschutes_taxlots --limit 100
```

## California Humboldt County setup

The California source uses Humboldt County's official Parcels (Owners) ArcGIS layer by default.
If needed, override `CA_HUMBOLDT_DATASET_URL` in `.env`.

Run it with:

```bash
python run_source.py ca_humboldt_parcels --limit 100
```

## Trust Bridge lead build (dialer-ready)

Use this command to build filtered homeowner leads for dialing:

```bash
python run_trust_bridge.py --sources ca_humboldt_parcels,or_deschutes_taxlots --states CA OR --per-source-limit 1000 --limit 250 --out data/trust_bridge_leads.csv
```

If you also want Excel output:

```bash
python run_trust_bridge.py --sources ca_humboldt_parcels,or_deschutes_taxlots --states CA OR --per-source-limit 1000 --limit 250 --out data/trust_bridge_leads.xlsx
```

Notes:
- Defaults keep only CA/OR residential homeowner rows and require dialable phone.
- Phone/age/income enrichment is optional and controlled with `TRUST_BRIDGE_ENRICHMENT_*` values in `.env`.
- If your source does not contain phone and no enrichment endpoint is configured, use `--allow-missing-phone` for a fallback export.

## CLI usage

### List supported sources

```bash
python -m scraper.cli sources
```

### Run a search

```bash
python -m scraper.cli search --source mock --limit 10 --format json --out data/results.json
```

Options:

- `--source`: source key, like `mock` or `la_open_data`
- `--limit`: number of rows to collect
- `--city`: optional filter passed to the source
- `--format`: `csv` or `json`
- `--out`: output file path
- `--sqlite`: optional SQLite database path

Example:

```bash
python -m scraper.cli search \
  --source mock \
  --limit 50 \
  --city "Los Angeles" \
  --format csv \
  --out data/results.csv \
  --sqlite data/results.db
```

## How to add a new county adapter

1. Create a new file in `scraper/sources/`.
2. Inherit from `PropertySource`.
3. Implement `fetch(limit: int, city: str | None = None) -> list[PropertyRecord]`.
4. Register it in `scraper/sources/registry.py`.

## Suggested next steps

1. Pick one exact LA County dataset
2. Configure `LA_DATASET_URL`
3. Adjust the field mappings
4. Verify the exported rows
5. Add a second county adapter later

## Notes on public-record workflow

Los Angeles County’s public resources indicate that parcel/open-data and property search are available, but ownership information requests may go through the Registrar-Recorder/County Clerk rather than always appearing in the open-data dataset itself. citeturn407791search1turn407791search2turn407791search11

That is why this codebase separates:
- source fetching,
- field mapping,
- normalization,
- export.
