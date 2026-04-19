from __future__ import annotations

from typing import Any

import requests

from scraper.config import OR_DESCHUTES_CONFIG
from scraper.models import PropertyRecord
from scraper.normalizer import clean_text, combine_address, normalize_record
from scraper.sources.base import PropertySource


class OregonDeschutesTaxlotsSource(PropertySource):
    key = "or_deschutes_taxlots"
    label = "Oregon Deschutes County Taxlots (ArcGIS FeatureServer)"

    # Relationship IDs from official Deschutes Taxlots layer:
    # 2=GIS_PCSTAT, 3=GIS_OWNERS, 4=GIS_MAILING, 5=GIS_ROLLVALUES, 7=GIS_ASSESSOR_ACCOUNT
    _REL_PCSTAT = 2
    _REL_OWNERS = 3
    _REL_MAILING = 4
    _REL_ROLLVALUES = 5
    _REL_ASSESSOR_ACCOUNT = 7

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        if not OR_DESCHUTES_CONFIG.dataset_url or not OR_DESCHUTES_CONFIG.related_url:
            raise ValueError(
                "OR_DESCHUTES_DATASET_URL / OR_DESCHUTES_RELATED_URL are not configured."
            )

        records: list[PropertyRecord] = []
        offset = 0
        page_size = max(1, min(OR_DESCHUTES_CONFIG.page_size, limit))

        while len(records) < limit:
            base_rows = self._fetch_base_page(page_size=page_size, offset=offset)
            if not base_rows:
                break

            object_ids = [row["OBJECTID"] for row in base_rows if "OBJECTID" in row]
            related = self._fetch_related_data(object_ids)

            for row in base_rows:
                obj_id = row.get("OBJECTID")
                if obj_id is None:
                    continue
                try:
                    record = self._map_record(row, related, obj_id)
                except Exception:
                    continue

                if city and clean_text(record.city).lower() != clean_text(city).lower():
                    continue

                records.append(record)
                if len(records) >= limit:
                    break

            offset += page_size

        return records

    def _fetch_base_page(self, page_size: int, offset: int) -> list[dict[str, Any]]:
        params = {
            "where": "1=1",
            "outFields": "OBJECTID,TAXLOT,MAPNUMBER",
            "f": "json",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "returnGeometry": "false",
        }
        response = requests.get(
            OR_DESCHUTES_CONFIG.dataset_url,
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

    def _fetch_related_data(self, object_ids: list[int]) -> dict[int, dict[str, dict[str, Any]]]:
        if not object_ids:
            return {}

        return {
            self._REL_OWNERS: self._fetch_related_records(object_ids, self._REL_OWNERS),
            self._REL_MAILING: self._fetch_related_records(object_ids, self._REL_MAILING),
            self._REL_PCSTAT: self._fetch_related_records(object_ids, self._REL_PCSTAT),
            self._REL_ROLLVALUES: self._fetch_related_records(object_ids, self._REL_ROLLVALUES),
            self._REL_ASSESSOR_ACCOUNT: self._fetch_related_records(
                object_ids, self._REL_ASSESSOR_ACCOUNT
            ),
        }

    def _fetch_related_records(
        self, object_ids: list[int], relationship_id: int
    ) -> dict[int, dict[str, Any]]:
        params = {
            "objectIds": ",".join(str(value) for value in object_ids),
            "relationshipId": relationship_id,
            "outFields": "*",
            "f": "json",
            "returnGeometry": "false",
        }
        response = requests.get(
            OR_DESCHUTES_CONFIG.related_url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        groups = payload.get("relatedRecordGroups", []) if isinstance(payload, dict) else []

        related_by_object_id: dict[int, dict[str, Any]] = {}
        for group in groups:
            object_id = group.get("objectId")
            records = group.get("relatedRecords", [])
            if not isinstance(object_id, int) or not isinstance(records, list):
                continue
            for related in records:
                attrs = related.get("attributes", {})
                if isinstance(attrs, dict):
                    related_by_object_id[object_id] = attrs
                    break
        return related_by_object_id

    def _map_record(
        self,
        base_row: dict[str, Any],
        related: dict[int, dict[int, dict[str, Any]]],
        object_id: int,
    ) -> PropertyRecord:
        owner = related[self._REL_OWNERS].get(object_id, {})
        mailing = related[self._REL_MAILING].get(object_id, {})
        pcstat = related[self._REL_PCSTAT].get(object_id, {})
        rollvalues = related[self._REL_ROLLVALUES].get(object_id, {})
        assessor = related[self._REL_ASSESSOR_ACCOUNT].get(object_id, {})

        property_address = combine_address(
            assessor.get("Address")
            or combine_address(
                assessor.get("House_Number"),
                assessor.get("Direction"),
                assessor.get("Street_Name"),
                assessor.get("Street_Type"),
                assessor.get("Unit_Number"),
            )
        )
        mailing_city = mailing.get("M_CITY")
        mailing_state = mailing.get("M_STATE")
        mailing_zip = mailing.get("M_ZIP")
        if not (mailing_city and mailing_state and mailing_zip):
            parsed_city, parsed_state, parsed_zip = self._parse_city_state_zip(
                clean_text(mailing.get("M_CITYSTZIP"))
            )
            mailing_city = mailing_city or parsed_city
            mailing_state = mailing_state or parsed_state
            mailing_zip = mailing_zip or parsed_zip

        mailing_address = combine_address(
            mailing.get("M_ADDRESS"),
            mailing_city,
            mailing_state,
            mailing_zip,
        )
        city = assessor.get("City") or ""
        state = assessor.get("State") or "OR"
        zip_code = assessor.get("Zip") or ""
        parcel_id = base_row.get("TAXLOT") or base_row.get("MAPNUMBER") or ""
        property_type = (
            pcstat.get("STAT_CLASS_DESC")
            or pcstat.get("PROPERTY_CLASS")
            or pcstat.get("STAT_CLASS")
            or ""
        )
        home_value = self._estimate_home_value(rollvalues)

        raw = {
            "base": base_row,
            "owner": owner,
            "mailing": mailing,
            "pcstat": pcstat,
            "rollvalues": rollvalues,
            "assessor": assessor,
            "estimated_home_value": home_value,
        }

        return normalize_record(
            raw,
            owner_name=owner.get("NAME") or mailing.get("OWNER") or "",
            property_address=property_address,
            mailing_address=mailing_address,
            city=city,
            state=state,
            zip_code=zip_code,
            parcel_id=parcel_id,
            property_type=property_type,
            source_url=OR_DESCHUTES_CONFIG.dataset_url,
        )

    def _estimate_home_value(self, rollvalues: dict[str, Any]) -> str:
        land = rollvalues.get("RMV_Land")
        impr = rollvalues.get("RMV_Impr")
        if isinstance(land, (int, float)) or isinstance(impr, (int, float)):
            land_num = float(land or 0)
            impr_num = float(impr or 0)
            return str(int(land_num + impr_num))
        return ""

    def _parse_city_state_zip(self, value: str) -> tuple[str, str, str]:
        if not value:
            return "", "", ""
        text = " ".join(part for part in value.replace(",", " ").split() if part)
        parts = text.split()
        if len(parts) < 2:
            return text, "", ""

        zip_code = parts[-1] if parts[-1].isdigit() else ""
        state = parts[-2] if len(parts[-2]) == 2 else ""
        city_parts = parts[:-2] if state else parts[:-1]
        city = " ".join(city_parts)
        return city, state, zip_code
