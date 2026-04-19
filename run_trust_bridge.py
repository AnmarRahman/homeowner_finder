from __future__ import annotations

import argparse
import os
from pathlib import Path

from scraper.trust_bridge_runner import (
    TrustBridgeRunConfig,
    parse_source_keys,
    parse_state_codes,
    run_trust_bridge,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Trust Bridge dialing leads from configured property sources."
    )
    parser.add_argument(
        "--sources",
        default=os.getenv("TRUST_BRIDGE_SOURCES", "ca_humboldt_parcels,or_deschutes_taxlots"),
        help="Comma-separated source keys (default: TRUST_BRIDGE_SOURCES or ca_humboldt_parcels,or_deschutes_taxlots).",
    )
    parser.add_argument(
        "--states",
        nargs="+",
        default=os.getenv("TRUST_BRIDGE_ALLOWED_STATES", "CA OR").split(),
        help="Allowed state codes (default: TRUST_BRIDGE_ALLOWED_STATES or CA OR).",
    )
    parser.add_argument(
        "--per-source-limit",
        type=int,
        default=int(os.getenv("TRUST_BRIDGE_PER_SOURCE_LIMIT", "500")),
        help="How many records to fetch per source before filtering.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("TRUST_BRIDGE_FINAL_LIMIT", "2000")),
        help="Final number of leads after filtering/deduplication.",
    )
    parser.add_argument("--city", default=None, help="Optional city filter passed to sources.")
    parser.add_argument(
        "--out",
        default=os.getenv("TRUST_BRIDGE_OUTPUT", "data/trust_bridge_leads.csv"),
        help="Output path. Use .csv or .xlsx.",
    )
    parser.add_argument(
        "--allow-missing-phone",
        action="store_true",
        help="Keep rows without dialable phones.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = TrustBridgeRunConfig(
        source_keys=parse_source_keys(args.sources),
        states=parse_state_codes(args.states),
        per_source_limit=args.per_source_limit,
        final_limit=args.limit,
        city=args.city,
        output_path=Path(args.out),
        allow_missing_phone=args.allow_missing_phone,
        prefer_owner_occupied=os.getenv("TRUST_BRIDGE_PREFER_OWNER_OCCUPIED", "1") == "1",
        free_phone_lookup_enabled=os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_ENABLED", "1")
        == "1",
        free_phone_lookup_use_browser=os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_USE_BROWSER", "1")
        == "1",
        free_phone_lookup_timeout_seconds=float(
            os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_TIMEOUT_SECONDS", "10")
        ),
        free_phone_lookup_delay_seconds=float(
            os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_DELAY_SECONDS", "0.2")
        ),
        free_phone_lookup_max_candidates=int(
            os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_MAX_CANDIDATES", "5")
        ),
        free_phone_lookup_max_per_run=int(
            os.getenv("TRUST_BRIDGE_FREE_PHONE_LOOKUP_MAX_PER_RUN", "2000")
        ),
    )

    try:
        result = run_trust_bridge(config)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if result.source_errors:
        for key, message in result.source_errors.items():
            print(f"Warning: source '{key}' failed: {message}")

    print(f"Collected {result.lead_count} lead(s).")
    if result.no_results_message:
        print(result.no_results_message)
    print(f"Saved output to: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
