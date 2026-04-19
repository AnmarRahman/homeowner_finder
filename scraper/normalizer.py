from __future__ import annotations

from typing import Any

from scraper.models import PropertyRecord


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value).strip()
    return str(value).replace("\n", " ").replace("\r", " ").strip()


def combine_address(*parts: Any) -> str:
    cleaned = [clean_text(part) for part in parts if clean_text(part)]
    return ", ".join(cleaned)


def normalize_record(
    raw: dict[str, Any],
    *,
    owner_name: Any = "",
    property_address: Any = "",
    mailing_address: Any = "",
    city: Any = "",
    state: Any = "CA",
    zip_code: Any = "",
    parcel_id: Any = "",
    property_type: Any = "",
    source_url: Any = "",
) -> PropertyRecord:
    return PropertyRecord(
        owner_name=clean_text(owner_name),
        property_address=clean_text(property_address),
        mailing_address=clean_text(mailing_address),
        city=clean_text(city),
        state=clean_text(state) or "CA",
        zip=clean_text(zip_code),
        parcel_id=clean_text(parcel_id),
        property_type=clean_text(property_type),
        source_url=clean_text(source_url),
        raw=raw,
    )
