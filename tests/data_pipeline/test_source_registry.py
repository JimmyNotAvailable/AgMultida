from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "metadata" / "source_registry.yaml"
SCAFFOLD_SECRET_SCAN_PATHS = [
    PROJECT_ROOT / "metadata",
    PROJECT_ROOT / "README_DATA_COLLECTION.md",
    PROJECT_ROOT / "README_DATA_PROCESSING.md",
    PROJECT_ROOT / "dataset_card.md",
    PROJECT_ROOT / "dvc.yaml",
    PROJECT_ROOT / ".dvc" / "config.example",
    PROJECT_ROOT / "reports" / "metadata_readiness_report.md",
    PROJECT_ROOT / "reports" / "realtime_readiness_report.md",
]


def test_source_registry_contains_required_public_sources():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))

    required_sources = {
        "sentinel2_gee",
        "sentinel2_stac",
        "era5_land",
        "chirps_gee",
        "chirps_direct",
        "smap",
        "open_meteo",
    }

    assert set(registry["sources"]) == required_sources


def test_source_registry_entries_are_traceable_and_dry_run_ready():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))

    for source_id, source in registry["sources"].items():
        assert source["id"] == source_id
        assert source["provider"]
        assert source["output_dir"].startswith("data/raw/")
        assert source["script"].startswith("scripts/")
        assert (PROJECT_ROOT / source["script"]).is_file()
        if "qa_script" in source:
            assert (PROJECT_ROOT / source["qa_script"]).is_file()
        if "process_script" in source:
            assert (PROJECT_ROOT / source["process_script"]).is_file()
        assert source["priority"] in {"P0", "P1", "optional_preferred", "optional", "disabled"}
        assert isinstance(source["enabled"], bool)
        assert isinstance(source["required"], bool)
        assert isinstance(source["auth_required"], bool)
        assert source["lookback_days"] == 14
        assert "latest_available_policy" in source
        assert "unavailable_statuses" in source
        assert all(
            status in registry["source_status_values"]
            for status in source["unavailable_statuses"]
        )
        assert source["credential_policy"] in {
            "none",
            "env_or_user_local_file",
            "earthengine_user_auth",
            "cdsapi_user_local_file",
            "direct_http",
            "public_stac",
        }


def test_source_required_optional_and_delay_policy_are_explicit():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    sources = registry["sources"]

    assert sources["sentinel2_gee"]["enabled"] is False
    assert sources["chirps_gee"]["enabled"] is False
    assert sources["sentinel2_gee"]["disabled_reason"] == "GEE_PROJECT_BILLING_BLOCKED"
    assert sources["chirps_gee"]["disabled_reason"] == "GEE_PROJECT_BILLING_BLOCKED"
    assert sources["sentinel2_stac"]["required"] is True
    assert sources["chirps_direct"]["required"] is True
    assert sources["open_meteo"]["required"] is True
    assert sources["era5_land"]["required"] is False
    assert sources["smap"]["required"] is False
    assert sources["open_meteo"]["auth_required"] is False
    assert "SOURCE_DELAYED" in registry["source_status_values"]
    assert "SOURCE_DELAYED" in sources["sentinel2_stac"]["unavailable_statuses"]
    assert "OPTIONAL_BLOCKED" in sources["era5_land"]["unavailable_statuses"]


def test_sentinel2_stac_and_chirps_direct_providers_are_declared():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    sentinel2_stac = registry["sources"]["sentinel2_stac"]
    chirps_direct = registry["sources"]["chirps_direct"]

    assert [provider["id"] for provider in sentinel2_stac["provider_priority"]] == [
        "aws_earth_search",
        "microsoft_planetary_computer",
        "copernicus_data_space",
    ]
    assert sentinel2_stac["provider_priority"][0]["stac_url"] == "https://earth-search.aws.element84.com/v1"
    assert sentinel2_stac["provider_priority"][0]["collection"] == "sentinel-2-c1-l2a"
    assert sentinel2_stac["bands"] == ["B02", "B03", "B04", "B08", "SCL"]
    assert chirps_direct["direct_base_url"].startswith("https://data.chc.ucsb.edu/products/CHIRPS-2.0/")
    assert chirps_direct["credential_policy"] == "direct_http"


def test_source_status_policy_prevents_fake_pass_for_blocked_or_delayed_sources():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    disallowed_pass_statuses = {"BLOCKED_AUTH", "SOURCE_DELAYED", "OPTIONAL_BLOCKED", "FAIL", "DISABLED"}

    for source in registry["sources"].values():
        assert "PASS" not in set(source["unavailable_statuses"])
        assert set(source["unavailable_statuses"]).issubset(disallowed_pass_statuses)

    assert "PASS" in registry["source_status_values"]


def test_scaffold_does_not_contain_real_secrets():
    scaffold_text = ""
    for path in SCAFFOLD_SECRET_SCAN_PATHS:
        if path.is_dir():
            scaffold_text += "\n".join(
                child.read_text(encoding="utf-8").lower()
                for child in sorted(path.rglob("*"))
                if child.is_file()
            )
        else:
            scaffold_text += path.read_text(encoding="utf-8").lower()

    forbidden_markers = [
        "api" + "_key:",
        "api" + "key:",
        "api" + "_key=",
        "api" + "key=",
        "pass" + "word:",
        "pass" + "word=",
        "to" + "ken:",
        "to" + "ken=",
        "sec" + "ret:",
        "sec" + "ret=",
        "bearer ",
        "earthdata" + "_password",
        "cdsapi" + "_key",
        "url:" + "uid:",
    ]

    assert not any(marker in scaffold_text for marker in forbidden_markers)
