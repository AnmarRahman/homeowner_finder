from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class PropertyRecord:
    owner_name: str = ""
    property_address: str = ""
    mailing_address: str = ""
    city: str = ""
    state: str = "CA"
    zip: str = ""
    parcel_id: str = ""
    property_type: str = ""
    source_url: str = ""
    raw: dict[str, Any] | list[Any] | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
