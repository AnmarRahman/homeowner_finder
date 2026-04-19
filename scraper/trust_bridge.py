from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from scraper.models import PropertyRecord
from scraper.normalizer import clean_text


RESIDENTIAL_SINGLE_FAMILY_KEYWORDS = (
    "single family",
    "single-family",
    "sfr",
    "sfh",
    "single family residence",
    "residential",
    "residence",
    "one story",
    "two story",
    "three story",
    "story",
    "house",
)
RESIDENTIAL_TOWNHOUSE_KEYWORDS = ("townhouse", "townhome")
RESIDENTIAL_MULTI_2_TO_4_KEYWORDS = ("duplex", "triplex", "quadplex", "fourplex", "2-4 unit")
EXCLUDED_PROPERTY_KEYWORDS = (
    "commercial",
    "industrial",
    "vacant",
    "land",
    "warehouse",
    "office",
    "retail",
)
INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "home_remodeling": ("remodel", "renovation", "renovate"),
    "kitchen_remodeling": ("kitchen remodel", "kitchen renovation"),
    "bathroom_remodeling": ("bath remodel", "bathroom remodel", "bathroom renovation"),
    "roofing": ("roof", "roofing", "reroof"),
    "solar": ("solar", "photovoltaic", "pv system"),
    "painting": ("paint", "painting"),
    "plumbing": ("plumb", "plumbing"),
    "concrete": ("concrete", "driveway"),
    "home_additions_adu": ("addition", "adu", "accessory dwelling unit"),
    "new_construction": ("new construction", "new build"),
}
RECENCY_KEYS = (
    "last_update",
    "last_updated",
    "updated_at",
    "update_date",
    "edit_date",
    "modified_date",
)
HOME_VALUE_KEYS = (
    "estimated_home_value",
    "home_value",
    "market_value",
    "assessed_value",
    "just_value",
    "total_value",
)
PHONE_KEYS = (
    "phone",
    "phone_number",
    "mobile_phone",
    "primary_phone",
)
AGE_KEYS = ("age", "owner_age", "estimated_age")
INCOME_KEYS = ("income", "income_level", "household_income", "estimated_income")
CSV_OWNER_KEYS = ("fullname", "ownername", "owner", "name")
CSV_ADDRESS_KEYS = ("propertyaddress", "address", "situsaddress", "streetaddress")
CSV_CITY_KEYS = ("city",)
CSV_STATE_KEYS = ("state",)
CSV_ZIP_KEYS = ("zip", "zipcode", "postalcode")
CSV_PHONE_KEYS = ("phonenumber", "phone", "mobilephone", "primaryphone", "cell", "cellphone")
CSV_AGE_KEYS = ("ownerage", "age", "estimatedage")
CSV_INCOME_KEYS = ("incomelevel", "income", "estimatedincome", "householdincome")
CSV_HOME_VALUE_KEYS = ("estimatedhomevalue", "homevalue", "marketvalue", "assessedvalue")
CSV_OWNER_OCCUPIED_KEYS = ("owneroccupied",)
CSV_OWNERSHIP_STATUS_KEYS = ("ownershipstatus",)
CSV_INTENT_TAGS_KEYS = ("intenttags",)

LEAD_FIELDS = [
    "full_name",
    "phone_number",
    "phone_status",
    "property_address",
    "city",
    "state",
    "zip_code",
    "ownership_status",
    "owner_occupied",
    "property_type",
    "estimated_home_value",
    "owner_age",
    "income_level",
    "intent_tags",
    "parcel_id",
    "source_key",
    "source_url",
    "last_updated",
    "raw",
]


@dataclass(slots=True)
class TrustBridgeLead:
    full_name: str = ""
    phone_number: str = ""
    phone_status: str = "missing"
    property_address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    ownership_status: str = ""
    owner_occupied: str = ""
    property_type: str = ""
    estimated_home_value: str = ""
    owner_age: str = ""
    income_level: str = ""
    intent_tags: str = ""
    parcel_id: str = ""
    source_key: str = ""
    source_url: str = ""
    last_updated: str = ""
    raw: dict[str, Any] | list[Any] | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TrustBridgeOptions:
    allowed_states: tuple[str, ...] = ("CA", "OR")
    require_dialable_phone: bool = True
    prefer_owner_occupied: bool = True
    enrichment_url: str = ""
    enrichment_api_key: str = ""
    enrichment_auth_header: str = "X-API-Key"
    enrichment_delay_seconds: float = 0.2
    enrichment_csv_path: str = ""


def build_trust_bridge_leads(
    *,
    source_to_records: dict[str, list[PropertyRecord]],
    final_limit: int,
    options: TrustBridgeOptions,
) -> list[TrustBridgeLead]:
    csv_index = load_csv_enrichment_index(options.enrichment_csv_path)
    candidates: list[TrustBridgeLead] = []
    for source_key, records in source_to_records.items():
        for record in records:
            lead = map_property_record(record=record, source_key=source_key)
            enrich_lead(lead, options, csv_index)
            if not lead_passes_filters(lead, options):
                continue
            candidates.append(lead)

    candidates.sort(key=lambda item: lead_priority_tuple(item, options), reverse=True)
    deduped = deduplicate_leads(candidates)
    return deduped[:final_limit]


def map_property_record(*, record: PropertyRecord, source_key: str) -> TrustBridgeLead:
    raw = record.raw if isinstance(record.raw, dict) else {}
    owner_name = clean_text(record.owner_name) or clean_text(find_first_by_key(raw, ("owner", "name")))
    property_type = infer_property_type(record)
    phone = normalize_phone(
        find_first_by_key(raw, PHONE_KEYS) or find_first_by_substring(raw, "phone")
    )
    phone_status = "dialable" if phone else "missing"

    lead = TrustBridgeLead(
        full_name=owner_name,
        phone_number=phone,
        phone_status=phone_status,
        property_address=clean_text(record.property_address),
        city=clean_text(record.city),
        state=clean_text(record.state),
        zip_code=clean_text(record.zip),
        ownership_status=infer_ownership_status(record, owner_name),
        owner_occupied="yes" if is_owner_occupied(record) else "no",
        property_type=property_type,
        estimated_home_value=clean_text(
            find_first_by_key(raw, HOME_VALUE_KEYS) or find_first_by_substring(raw, "value")
        ),
        owner_age=clean_text(find_first_by_key(raw, AGE_KEYS)),
        income_level=clean_text(find_first_by_key(raw, INCOME_KEYS)),
        intent_tags=infer_intent_tags(record),
        parcel_id=clean_text(record.parcel_id),
        source_key=source_key,
        source_url=clean_text(record.source_url),
        last_updated=extract_last_updated(raw),
        raw=record.raw,
    )
    return lead


def enrich_lead(
    lead: TrustBridgeLead,
    options: TrustBridgeOptions,
    csv_index: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> None:
    enrich_lead_from_csv(lead, csv_index)
    if (
        lead.phone_number
        and lead.owner_age
        and lead.income_level
        and lead.estimated_home_value
        and lead.intent_tags
    ):
        return
    enrich_lead_from_api(lead, options)


def enrich_lead_from_api(lead: TrustBridgeLead, options: TrustBridgeOptions) -> None:
    if not options.enrichment_url:
        return

    payload = {
        "full_name": lead.full_name,
        "property_address": lead.property_address,
        "city": lead.city,
        "state": lead.state,
        "zip_code": lead.zip_code,
        "parcel_id": lead.parcel_id,
    }
    headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    if options.enrichment_api_key:
        headers[options.enrichment_auth_header] = options.enrichment_api_key

    response = requests.post(
        options.enrichment_url,
        headers=headers,
        data=json.dumps(payload),
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        return

    enriched_phone = normalize_phone(
        body.get("phone_number") or body.get("phone") or lead.phone_number
    )
    lead.phone_number = enriched_phone
    lead.phone_status = "dialable" if enriched_phone else lead.phone_status
    lead.owner_age = clean_text(body.get("owner_age") or body.get("age") or lead.owner_age)
    lead.income_level = clean_text(
        body.get("income_level") or body.get("income") or lead.income_level
    )
    lead.estimated_home_value = clean_text(
        body.get("estimated_home_value")
        or body.get("home_value")
        or lead.estimated_home_value
    )
    lead.ownership_status = clean_text(body.get("ownership_status") or lead.ownership_status)
    if "owner_occupied" in body:
        lead.owner_occupied = "yes" if bool(body["owner_occupied"]) else "no"

    tags = body.get("intent_tags")
    if isinstance(tags, list):
        lead.intent_tags = ";".join(sorted(clean_text(tag) for tag in tags if clean_text(tag)))
    elif isinstance(tags, str) and clean_text(tags):
        lead.intent_tags = clean_text(tags)

    if options.enrichment_delay_seconds > 0:
        time.sleep(options.enrichment_delay_seconds)


def enrich_lead_from_csv(
    lead: TrustBridgeLead,
    csv_index: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> None:
    if not csv_index:
        return

    candidate = find_csv_enrichment_candidate(lead, csv_index)
    if not candidate:
        return

    phone = normalize_phone(candidate.get("phone_number", ""))
    if phone:
        lead.phone_number = phone
        lead.phone_status = "dialable"

    if not lead.owner_age:
        lead.owner_age = clean_text(candidate.get("owner_age"))
    if not lead.income_level:
        lead.income_level = clean_text(candidate.get("income_level"))
    if not lead.estimated_home_value:
        lead.estimated_home_value = clean_text(candidate.get("estimated_home_value"))
    if not lead.ownership_status:
        lead.ownership_status = clean_text(candidate.get("ownership_status"))
    if not lead.intent_tags:
        lead.intent_tags = clean_text(candidate.get("intent_tags"))

    owner_occupied = clean_text(candidate.get("owner_occupied")).lower()
    if owner_occupied in {"yes", "y", "true", "1"}:
        lead.owner_occupied = "yes"
    elif owner_occupied in {"no", "n", "false", "0"}:
        lead.owner_occupied = "no"


def lead_passes_filters(lead: TrustBridgeLead, options: TrustBridgeOptions) -> bool:
    if lead.state.upper() not in {state.upper() for state in options.allowed_states}:
        return False
    if not lead.full_name:
        return False
    if lead.ownership_status.lower() in {"unknown", ""}:
        return False
    if not is_residential_allowed_type(lead.property_type):
        return False
    if options.require_dialable_phone and not is_dialable_phone(lead.phone_number):
        return False
    return True


def deduplicate_leads(leads: Iterable[TrustBridgeLead]) -> list[TrustBridgeLead]:
    deduped: list[TrustBridgeLead] = []
    seen: set[tuple[str, str, str, str]] = set()
    for lead in leads:
        key = lead_identity_key(lead)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(lead)
    return deduped


def lead_identity_key(lead: TrustBridgeLead) -> tuple[str, str, str, str]:
    state = clean_text(lead.state).upper()
    parcel = normalize_address_for_compare(lead.parcel_id)
    addr = normalize_address_for_compare(lead.property_address)
    city = normalize_address_for_compare(lead.city)
    owner = normalize_name_for_compare(lead.full_name)

    if parcel:
        return ("parcel", state, parcel, "")
    if addr and owner:
        return ("owner_addr", state, addr, owner)
    if addr:
        return ("addr", state, addr, city)
    if owner and clean_text(lead.zip_code):
        return ("owner_zip", state, owner, clean_text(lead.zip_code))
    return ("fallback", state, owner, normalize_phone_digits(lead.phone_number))


def lead_priority_tuple(lead: TrustBridgeLead, options: TrustBridgeOptions) -> tuple[int, int, float]:
    owner_occupied_weight = 1 if lead.owner_occupied == "yes" else 0
    if not options.prefer_owner_occupied:
        owner_occupied_weight = 0
    dialable_weight = 1 if is_dialable_phone(lead.phone_number) else 0
    recency = recency_score(lead.last_updated)
    return (owner_occupied_weight, dialable_weight, recency)


def infer_property_type(record: PropertyRecord) -> str:
    raw = record.raw if isinstance(record.raw, dict) else {}
    pcstat = raw.get("pcstat", {}) if isinstance(raw.get("pcstat", {}), dict) else {}
    property_class = clean_text(pcstat.get("PROPERTY_CLASS"))
    stat_class = clean_text(pcstat.get("STAT_CLASS"))

    if property_class.startswith("4"):
        if stat_class.startswith(("18", "19")):
            return ""
        return "single_family"

    raw_text = " ".join(
        [
            clean_text(record.property_type),
            clean_text(find_first_by_substring(raw, "property_type")),
            clean_text(find_first_by_substring(raw, "land_use")),
            clean_text(find_first_by_substring(raw, "use")),
            clean_text(find_first_by_substring(raw, "class")),
            clean_text(find_first_by_substring(raw, "zoning")),
        ]
    ).lower()
    if any(token in raw_text for token in EXCLUDED_PROPERTY_KEYWORDS):
        return ""
    if any(token in raw_text for token in RESIDENTIAL_TOWNHOUSE_KEYWORDS):
        return "townhouse"
    if any(token in raw_text for token in RESIDENTIAL_MULTI_2_TO_4_KEYWORDS):
        return "duplex_triplex_quadplex"
    if any(token in raw_text for token in RESIDENTIAL_SINGLE_FAMILY_KEYWORDS):
        return "single_family"
    return ""


def infer_ownership_status(record: PropertyRecord, owner_name: str) -> str:
    raw = record.raw if isinstance(record.raw, dict) else {}
    explicit = clean_text(find_first_by_substring(raw, "ownership"))
    if explicit:
        lowered = explicit.lower()
        if "tenant" in lowered or "renter" in lowered:
            return "tenant"
        if "owner" in lowered:
            return "homeowner"
    return "homeowner" if owner_name else "unknown"


def is_owner_occupied(record: PropertyRecord) -> bool:
    raw = record.raw if isinstance(record.raw, dict) else {}
    ownocc = clean_text(raw.get("OWNOCC")).upper()
    if ownocc in {"Y", "YES", "1", "TRUE"}:
        return True
    if ownocc in {"N", "NO", "0", "FALSE"}:
        return False

    prop = normalize_address_for_compare(record.property_address)
    mail = normalize_address_for_compare(record.mailing_address)
    return bool(prop and mail and prop == mail)


def is_residential_allowed_type(property_type: str) -> bool:
    return property_type in {"single_family", "townhouse", "duplex_triplex_quadplex"}


def infer_intent_tags(record: PropertyRecord) -> str:
    text_parts = [
        clean_text(record.property_type),
        clean_text(record.property_address),
        clean_text(record.mailing_address),
    ]
    if isinstance(record.raw, dict):
        text_parts.append(json.dumps(record.raw, ensure_ascii=False))
    corpus = " ".join(text_parts).lower()

    matched: list[str] = []
    for tag, keywords in INTENT_KEYWORDS.items():
        if any(keyword in corpus for keyword in keywords):
            matched.append(tag)
    return ";".join(sorted(matched))


def extract_last_updated(raw: dict[str, Any]) -> str:
    value = find_first_by_key(raw, RECENCY_KEYS)
    return clean_text(value)


def recency_score(value: str) -> float:
    if not value:
        return 0.0
    parsed = parse_possible_datetime(value)
    if not parsed:
        return 0.0
    return parsed.timestamp()


def parse_possible_datetime(value: str) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None

    if text.isdigit():
        number = int(text)
        if number > 999999999999:
            return datetime.fromtimestamp(number / 1000, tz=timezone.utc)
        if number > 999999999:
            return datetime.fromtimestamp(number, tz=timezone.utc)

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def find_first_by_key(raw: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in raw and clean_text(raw[key]):
            return raw[key]
    lower_lookup = {str(key).lower(): key for key in raw.keys()}
    for key in keys:
        matched = lower_lookup.get(key.lower())
        if matched is not None and clean_text(raw[matched]):
            return raw[matched]
    return ""


def find_first_by_substring(raw: dict[str, Any], text: str) -> Any:
    target = text.lower()
    for key, value in raw.items():
        if target in str(key).lower() and clean_text(value):
            return value
    return ""


def load_csv_enrichment_index(
    path_value: str,
) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    path_text = clean_text(path_value)
    if not path_text:
        return {}

    path = Path(path_text)
    if not path.exists():
        raise ValueError(f"Enrichment CSV file not found: {path}")

    index: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = normalize_enrichment_row(row)
            if not normalized:
                continue
            for key in enrichment_row_identity_keys(normalized):
                index.setdefault(key, []).append(normalized)
    return index


def normalize_enrichment_row(row: dict[str, Any] | None) -> dict[str, str]:
    if not row:
        return {}

    normalized_row = {normalize_header(key): clean_text(value) for key, value in row.items()}
    owner = pick_csv_value(normalized_row, CSV_OWNER_KEYS)
    address = pick_csv_value(normalized_row, CSV_ADDRESS_KEYS)
    city = pick_csv_value(normalized_row, CSV_CITY_KEYS)
    state = pick_csv_value(normalized_row, CSV_STATE_KEYS).upper()
    zip_code = pick_csv_value(normalized_row, CSV_ZIP_KEYS)
    phone = normalize_phone(pick_csv_value(normalized_row, CSV_PHONE_KEYS))

    if not address and not owner:
        return {}

    return {
        "full_name": owner,
        "property_address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "phone_number": phone,
        "owner_age": pick_csv_value(normalized_row, CSV_AGE_KEYS),
        "income_level": pick_csv_value(normalized_row, CSV_INCOME_KEYS),
        "estimated_home_value": pick_csv_value(normalized_row, CSV_HOME_VALUE_KEYS),
        "owner_occupied": pick_csv_value(normalized_row, CSV_OWNER_OCCUPIED_KEYS),
        "ownership_status": pick_csv_value(normalized_row, CSV_OWNERSHIP_STATUS_KEYS),
        "intent_tags": pick_csv_value(normalized_row, CSV_INTENT_TAGS_KEYS),
    }


def enrichment_row_identity_keys(row: dict[str, str]) -> list[tuple[str, str, str, str]]:
    state = normalize_address_for_compare(row.get("state", ""))
    owner = normalize_name_for_compare(row.get("full_name", ""))
    address = normalize_address_for_compare(row.get("property_address", ""))
    city = normalize_address_for_compare(row.get("city", ""))
    zip_code = normalize_address_for_compare(row.get("zip_code", ""))

    keys: list[tuple[str, str, str, str]] = []
    if address and state and zip_code:
        keys.append(("addr_state_zip", state, address, zip_code))
    if address and state and city:
        keys.append(("addr_state_city", state, address, city))
    if owner and address and state:
        keys.append(("owner_addr_state", state, owner, address))
    return keys


def find_csv_enrichment_candidate(
    lead: TrustBridgeLead,
    csv_index: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> dict[str, str]:
    state = normalize_address_for_compare(lead.state)
    owner = normalize_name_for_compare(lead.full_name)
    address = normalize_address_for_compare(lead.property_address)
    city = normalize_address_for_compare(lead.city)
    zip_code = normalize_address_for_compare(lead.zip_code)

    keys: list[tuple[str, str, str, str]] = []
    if address and state and zip_code:
        keys.append(("addr_state_zip", state, address, zip_code))
    if address and state and city:
        keys.append(("addr_state_city", state, address, city))
    if owner and address and state:
        keys.append(("owner_addr_state", state, owner, address))

    for key in keys:
        candidates = csv_index.get(key, [])
        if not candidates:
            continue
        return max(candidates, key=enrichment_row_quality_score)
    return {}


def enrichment_row_quality_score(row: dict[str, str]) -> tuple[int, int]:
    has_phone = 1 if is_dialable_phone(row.get("phone_number", "")) else 0
    quality = sum(
        1
        for key in ("owner_age", "income_level", "estimated_home_value", "ownership_status", "intent_tags")
        if clean_text(row.get(key))
    )
    return (has_phone, quality)


def normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


def pick_csv_value(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = clean_text(row.get(alias, ""))
        if value:
            return value
    return ""


def normalize_phone(value: Any) -> str:
    digits = normalize_phone_digits(value)
    if not digits:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def normalize_phone_digits(value: Any) -> str:
    digits = re.sub(r"\D", "", clean_text(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    if digits in {"0000000000", "1111111111", "1234567890"}:
        return ""
    if int(digits[0:3]) < 200 or int(digits[3:6]) < 200:
        return ""
    return digits


def is_dialable_phone(phone_number: str) -> bool:
    return bool(normalize_phone_digits(phone_number))


def normalize_address_for_compare(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


def normalize_name_for_compare(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


def export_trust_bridge_leads_csv(
    leads: Iterable[TrustBridgeLead], output_path: str | Path
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEAD_FIELDS)
        writer.writeheader()
        for lead in leads:
            row = lead.to_dict()
            row["raw"] = json.dumps(row["raw"], ensure_ascii=False)
            writer.writerow(row)
    return path
