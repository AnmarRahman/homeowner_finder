from pathlib import Path

from scraper.trust_bridge_runner import TrustBridgeRunConfig, run_trust_bridge


def test_run_trust_bridge_with_mock_source() -> None:
    output_path = Path("data") / "runner_test_output.csv"
    config = TrustBridgeRunConfig(
        source_keys=["mock"],
        states=("CA",),
        per_source_limit=25,
        final_limit=10,
        city=None,
        output_path=output_path,
        allow_missing_phone=True,
        prefer_owner_occupied=True,
    )

    result = run_trust_bridge(config)

    assert result.lead_count == 10
    assert result.output_path == output_path
    assert output_path.exists()
    assert result.source_errors == {}
    assert result.no_results_message == ""
