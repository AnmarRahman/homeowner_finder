from __future__ import annotations

from typing import Any

import requests

from scraper.config import CA_HUMBOLDT_CONFIG
from scraper.models import PropertyRecord
from scraper.normalizer import clean_text, combine_address, normalize_record
from scraper.sources.base import PropertySource


class CaliforniaHumboldtParcelsSource(PropertySource):
    key = "ca_humboldt_parcels"
    label = "California Humboldt County Parcels (Owners)"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        if not CA_HUMBOLDT_CONFIG.dataset_url:
            raise ValueError(
                "CA_HUMBOLDT_DATASET_URL is not configured. "
                "Add a valid ArcGIS query endpoint to .env."
            )

        records: list[PropertyRecord] = []
        offset = 0
        page_size = max(1, min(CA_HUMBOLDT_CONFIG.page_size, limit))

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
        if city and CA_HUMBOLDT_CONFIG.city_filter_param:
            where_clause += f" AND {CA_HUMBOLDT_CONFIG.city_filter_param} = '{city}'"

        params = {
            "where": where_clause,
            "outFields": "*",
            "f": "json",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "returnGeometry": "false",
        }
        response = requests.get(
            CA_HUMBOLDT_CONFIG.dataset_url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features", []) if isinstance(payload, dict) else []

        rows: list[dict[str, Any]] = []
        for feature in features:
            attrs = feature.get("attributes", {})
            if isinstance(attrs, dict):
                rows.append(attrs)
        return rows

    def _map_record(self, raw: dict[str, Any]) -> PropertyRecord:
        mailing_address = combine_address(
            raw.get("ADDRESS1"),
            raw.get("ADDRESS2"),
            raw.get("ADDRESS3"),
            raw.get("CITY"),
            raw.get("STATE"),
            raw.get("ZIP"),
        )
        value = self._estimate_home_value(raw)
        raw_with_value = dict(raw)
        raw_with_value["estimated_home_value"] = value

        return normalize_record(
            raw_with_value,
            owner_name=raw.get("NAME") or "",
            property_address=raw.get("FULLADDR") or "",
            mailing_address=mailing_address,
            city=raw.get("SITCITY") or "",
            state="CA",
            zip_code=raw.get("SITZIP") or "",
            parcel_id=raw.get("APN_12") or raw.get("APN") or "",
            property_type=raw.get("DESCRIPTIO") or "",
            source_url=CA_HUMBOLDT_CONFIG.dataset_url,
        )

    def _estimate_home_value(self, raw: dict[str, Any]) -> str:
        land = raw.get("LAND")
        impr = raw.get("IMPR")
        if isinstance(land, (int, float)) or isinstance(impr, (int, float)):
            land_num = float(land or 0)
            impr_num = float(impr or 0)
            return str(int(land_num + impr_num))
        return clean_text(raw.get("LAND") or "")
