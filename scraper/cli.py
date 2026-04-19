from __future__ import annotations

import argparse
from pathlib import Path

from scraper.exporters import export_csv, export_json
from scraper.sources import get_source, list_sources
from scraper.storage import SQLiteStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="California homeowner/property data collector")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources_parser = subparsers.add_parser("sources", help="List supported data sources")
    sources_parser.set_defaults(func=handle_sources)

    search_parser = subparsers.add_parser("search", help="Run a property search")
    search_parser.add_argument("--source", required=True, help="Source key, e.g. mock or la_open_data")
    search_parser.add_argument("--limit", type=int, default=25, help="Number of records to fetch")
    search_parser.add_argument("--city", default=None, help="Optional city filter")
    search_parser.add_argument("--format", choices=["csv", "json"], default="csv")
    search_parser.add_argument("--out", required=True, help="Output file path")
    search_parser.add_argument("--sqlite", default=None, help="Optional SQLite DB path")
    search_parser.set_defaults(func=handle_search)

    return parser


def handle_sources(_args: argparse.Namespace) -> int:
    for key, label in list_sources():
        print(f"{key}: {label}")
    return 0


def handle_search(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")

    source = get_source(args.source)
    records = source.fetch(limit=args.limit, city=args.city)

    output_path = Path(args.out)
    if args.format == "csv":
        export_csv(records, output_path)
    else:
        export_json(records, output_path)

    if args.sqlite:
        SQLiteStorage(args.sqlite).save(records)

    print(f"Fetched {len(records)} record(s) from '{args.source}'.")
    print(f"Saved output to: {output_path}")
    if args.sqlite:
        print(f"Saved SQLite data to: {args.sqlite}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
