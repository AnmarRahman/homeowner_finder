from __future__ import annotations

from scraper.sources.base import PropertySource
from scraper.sources.broward_bcpa import BrowardBCPASource
from scraper.sources.ca_humboldt_parcels import CaliforniaHumboldtParcelsSource
from scraper.sources.la_open_data import LAOpenDataSource
from scraper.sources.mock_source import MockPropertySource
from scraper.sources.or_deschutes_taxlots import OregonDeschutesTaxlotsSource


SOURCES: dict[str, PropertySource] = {
    "mock": MockPropertySource(),
    "la_open_data": LAOpenDataSource(),
    "ca_humboldt_parcels": CaliforniaHumboldtParcelsSource(),
    "broward_bcpa": BrowardBCPASource(),
    "or_deschutes_taxlots": OregonDeschutesTaxlotsSource(),
}


def get_source(key: str) -> PropertySource:
    try:
        return SOURCES[key]
    except KeyError as exc:
        supported = ", ".join(sorted(SOURCES))
        raise KeyError(f"Unknown source '{key}'. Supported sources: {supported}") from exc


def list_sources() -> list[tuple[str, str]]:
    return sorted((key, source.label) for key, source in SOURCES.items())
