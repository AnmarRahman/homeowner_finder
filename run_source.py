from __future__ import annotations

import argparse
from pathlib import Path

from scraper.exporters import export_csv
from scraper.sources import get_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a property source and save CSV output."
    )
    parser.add_argument("source", help="Source key, e.g. broward_bcpa or la_open_data")
    parser.add_argument("--limit", type=int, default=25, help="Number of records to fetch")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output CSV path (default: data/<source>_results.csv)",
    )
    parser.add_argument("--city", default=None, help="Optional city filter")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")

    source = get_source(args.source)
    records = source.fetch(limit=args.limit, city=args.city)

    output_path = Path(args.out) if args.out else Path("data") / f"{args.source}_results.csv"
    export_csv(records, output_path)

    print(f"Fetched {len(records)} record(s) from '{args.source}'.")
    print(f"Saved output to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
