from __future__ import annotations

from typing import Any

import requests

from scraper.config import LA_CONFIG
from scraper.models import PropertyRecord
from scraper.normalizer import normalize_record
from scraper.sources.base import PropertySource


class LAOpenDataSource(PropertySource):
    key = "la_open_data"
    label = "Los Angeles County Parcel Layer (ArcGIS FeatureServer)"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        if not LA_CONFIG.dataset_url:
            raise ValueError(
                "LA_DATASET_URL is not configured. Add a valid ArcGIS FeatureServer endpoint to .env."
            )

        records: list[PropertyRecord] = []
        offset = 0
        page_size = max(1, min(LA_CONFIG.page_size, limit))

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

        if city and LA_CONFIG.city_filter_param:
            where_clause += f" AND {LA_CONFIG.city_filter_param} = '{city}'"

        params: dict[str, Any] = {
            "where": where_clause,
            "outFields": "*",
            "f": "json",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "returnGeometry": "false",
        }

        response = requests.get(
            LA_CONFIG.dataset_url,
            params=params,
            headers={"Accept": "application/json"},
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
        def pick(config_key: str, *fallback_keys: str) -> Any:
            if config_key and raw.get(config_key):
                return raw.get(config_key)
            for key in fallback_keys:
                if raw.get(key):
                    return raw.get(key)
            return ""

        owner_name = pick(LA_CONFIG.field_owner, "owner_name", "OWNER_NAME", "OWNER", "Taxpayer")
        property_address = pick(
            LA_CONFIG.field_property_address,
            "property_address",
            "PROPERTY_ADDRESS",
            "SITUS_ADDRESS",
            "SITE_ADDR",
        )
        mailing_address = pick(
            LA_CONFIG.field_mailing_address,
            "mailing_address",
            "MAILING_ADDRESS",
            "MAIL_ADDR",
        )
        city = pick(LA_CONFIG.field_city, "city", "CITY", "MUNICIPALITY")
        state = pick(LA_CONFIG.field_state, "state", "STATE")
        zip_code = pick(LA_CONFIG.field_zip, "zip", "ZIP", "ZIP_CODE")
        parcel_id = pick(LA_CONFIG.field_parcel_id, "parcel_id", "PARCEL_ID", "APN", "APNI")
        property_type = pick(
            LA_CONFIG.field_property_type, "property_type", "PROPERTY_TYPE", "USE_CODE"
        )
        source_url = raw.get("LACO_URL") or LA_CONFIG.dataset_url

        return normalize_record(
            raw,
            owner_name=owner_name,
            property_address=property_address,
            mailing_address=mailing_address,
            city=city,
            state=state or "CA",
            zip_code=zip_code,
            parcel_id=parcel_id,
            property_type=property_type,
            source_url=source_url,
        )
