from scraper import app_update
from scraper.app_update import get_manifest_url, is_newer_version, parse_version


def test_parse_version_extracts_numeric_triplet() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v2.0") == (2, 0, 0)
    assert parse_version("3") == (3, 0, 0)


def test_is_newer_version_compares_semver_like_values() -> None:
    assert is_newer_version("1.0.1", "1.0.0")
    assert is_newer_version("1.2.0", "1.1.9")
    assert not is_newer_version("1.0.0", "1.0.0")
    assert not is_newer_version("1.0.0", "1.0.1")


def test_get_manifest_url_defaults_when_config_missing(monkeypatch) -> None:
    monkeypatch.delenv("TRUST_BRIDGE_UPDATE_MANIFEST_URL", raising=False)
    missing_path = app_update.Path.cwd() / "_missing_update_config.json"
    if missing_path.exists():
        missing_path.unlink()
    monkeypatch.setattr(app_update, "get_update_config_path", lambda: missing_path)
    assert get_manifest_url() == app_update.DEFAULT_MANIFEST_URL


def test_get_manifest_url_uses_config_override(monkeypatch) -> None:
    monkeypatch.delenv("TRUST_BRIDGE_UPDATE_MANIFEST_URL", raising=False)
    config_path = app_update.Path.cwd() / "_test_update_config.json"
    monkeypatch.setattr(app_update, "get_update_config_path", lambda: config_path)
    try:
        config_path.write_text(
            '{"manifest_url":"https://example.com/custom-latest.json"}',
            encoding="utf-8",
        )
        assert get_manifest_url() == "https://example.com/custom-latest.json"
    finally:
        config_path.unlink(missing_ok=True)
