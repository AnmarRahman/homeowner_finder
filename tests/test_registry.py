from scraper.sources.registry import get_source, list_sources


def test_list_sources_contains_mock() -> None:
    keys = [key for key, _label in list_sources()]
    assert "mock" in keys
    assert "broward_bcpa" in keys
    assert "or_deschutes_taxlots" in keys
    assert "ca_humboldt_parcels" in keys


def test_get_source_returns_mock() -> None:
    source = get_source("mock")
    assert source.key == "mock"
