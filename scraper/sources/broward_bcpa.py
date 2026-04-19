from __future__ import annotations

from typing import Any

import requests

from scraper.config import BROWARD_CONFIG
from scraper.models import PropertyRecord
from scraper.normalizer import combine_address, normalize_record
from scraper.sources.base import PropertySource


class BrowardBCPASource(PropertySource):
    key = "broward_bcpa"
    label = "Broward County Property Appraiser Parcels (ArcGIS FeatureServer)"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        if not BROWARD_CONFIG.dataset_url:
            raise ValueError(
                "BROWARD_DATASET_URL is not configured. Add a valid ArcGIS FeatureServer /query endpoint to .env."
            )

        records: list[PropertyRecord] = []
        offset = 0
        page_size = max(1, min(BROWARD_CONFIG.page_size, limit))

        while len(records) < limit:
            batch = self._fetch_page(page_size=page_size, offset=offset, city=city)
            if not batch:
                break

            for raw in batch:
                try:
                    records.append(self._map_record(raw))
                except Exception:
                    continue

                if len(records) >= limit:
                    break

            offset += page_size

        return records

    def _fetch_page(
        self,
        page_size: int,
        offset: int,
        city: str | None,
    ) -> list[dict[str, Any]]:
        where_clause = "1=1"
        if city and BROWARD_CONFIG.city_filter_param:
            where_clause += f" AND {BROWARD_CONFIG.city_filter_param} = '{city}'"

        params: dict[str, Any] = {
            "where": where_clause,
            "outFields": "*",
            "f": "json",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "returnGeometry": "false",
        }

        response = requests.get(
            BROWARD_CONFIG.dataset_url,
            params=params,
            headers={
                "Accept": "application/json",
                "User-Agent": "homeowner-finder/1.0",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise ValueError(
                f"Expected JSON but got Content-Type={content_type!r}. "
                f"First 300 chars: {response.text[:300]!r}"
            )

        payload = response.json()
        if not isinstance(payload, dict) or "features" not in payload:
            raise ValueError(
                f"Expected ArcGIS JSON with 'features'. Got: {str(payload)[:300]}"
            )

        rows: list[dict[str, Any]] = []
        for feature in payload.get("features", []):
            attrs = feature.get("attributes", {})
            if isinstance(attrs, dict):
                rows.append(attrs)

        return rows

    def _map_record(self, raw: dict[str, Any]) -> PropertyRecord:
        owner_name = " ".join(
            part for part in [raw.get("NAME_LINE_"), raw.get("NAME_LINE1")] if part
        )

        property_address = self._build_situs_address(raw)
        mailing_address = combine_address(
            raw.get("ADDRESS_LI"),
            raw.get("CITY"),
            raw.get("STATE"),
            raw.get("ZIP"),
        )

        return normalize_record(
            raw,
            owner_name=owner_name,
            property_address=property_address,
            mailing_address=mailing_address,
            city=raw.get("CITY") or "",
            state=raw.get("STATE") or "FL",
            zip_code=raw.get("ZIP") or "",
            parcel_id=raw.get("FOLIO") or "",
            property_type="",
            source_url=BROWARD_CONFIG.dataset_url,
        )

    def _build_situs_address(self, raw: dict[str, Any]) -> str:
        parts = [
            raw.get("SITUS_STRE"),
            raw.get("SITUS_ST_2"),
            raw.get("SITUS_ST_4"),
            raw.get("SITUS_ST_5"),
        ]
        street = " ".join(str(part).strip() for part in parts if part)
        unit = raw.get("SITUS_UNIT")
        if unit:
            street = f"{street} {str(unit).strip()}"
        return street.strip()
