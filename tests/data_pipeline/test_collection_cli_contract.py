import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMON_PATH = PROJECT_ROOT / "scripts" / "data_collection_common.py"
SCRIPT_ENTRYPOINTS = [
    path
    for path in sorted((PROJECT_ROOT / "scripts").glob("*.py"))
    if path.name != "data_collection_common.py"
]


def load_common_module():
    spec = importlib.util.spec_from_file_location("data_collection_common", COMMON_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_project_path_rejects_parent_traversal():
    common = load_common_module()

    try:
        common.safe_project_path("../outside")
    except ValueError as error:
        assert "outside project root" in str(error)
    else:
        raise AssertionError("unsafe parent traversal path was accepted")


def test_safe_writable_path_rejects_parent_traversal():
    common = load_common_module()

    try:
        common.safe_writable_path("../outside")
    except ValueError as error:
        assert "outside allowed writable roots" in str(error)
    else:
        raise AssertionError("unsafe writable parent traversal path was accepted")


def test_all_script_entrypoints_expose_dry_run_help():
    assert SCRIPT_ENTRYPOINTS

    for script_path in SCRIPT_ENTRYPOINTS:
        result = subprocess.run(
            ["python3", str(script_path), "--help"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        assert "--dry-run" in result.stdout


def test_download_script_dry_run_creates_output_dir_and_appends_log():
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "sentinel2"
        download_log = Path(tmp_dir) / "download_log.json"

        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "download_sentinel2_stac.py"),
                "--dry-run",
                "--output-dir",
                str(output_dir),
                "--download-log",
                str(download_log),
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2023-01-02",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        log_payload = json.loads(download_log.read_text(encoding="utf-8"))

        assert payload["status"] == "PASS"
        assert payload["writes_primary_data"] is False
        assert output_dir.is_dir()
        assert log_payload["entries"][0]["source_id"] == "sentinel2_stac"
        assert log_payload["entries"][0]["status"] == "PASS"


def test_download_script_real_mode_is_explicitly_blocked():
    with tempfile.TemporaryDirectory() as tmp_dir:
        download_log = Path(tmp_dir) / "download_log.json"

        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "download_open_meteo.py"),
                "--download-log",
                str(download_log),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        log_payload = json.loads(download_log.read_text(encoding="utf-8"))

        assert result.returncode == 2
        assert "APPROVE DATA REAL DOWNLOAD" in result.stderr
        assert log_payload["entries"][0]["status"] == "BLOCKED_AUTH"


def test_run_data_collection_dry_run_writes_report_and_log():
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "coverage_report.csv"
        download_log = Path(tmp_dir) / "download_log.json"

        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "run_data_collection.py"),
                "--dry-run",
                "--coverage-report",
                str(report_path),
                "--download-log",
                str(download_log),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        report_text = report_path.read_text(encoding="utf-8")
        log_payload = json.loads(download_log.read_text(encoding="utf-8"))

        assert payload["status"] == "PASS"
        assert payload["sources_checked"] == 7
        assert "sentinel2_stac,PASS" in report_text
        assert "sentinel2_gee,DISABLED" in report_text
        assert "chirps_direct,PASS" in report_text
        assert len(log_payload["entries"]) == 7


def test_disabled_gee_source_dry_run_returns_disabled_without_blocking():
    with tempfile.TemporaryDirectory() as tmp_dir:
        download_log = Path(tmp_dir) / "download_log.json"

        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "download_sentinel2_gee.py"),
                "--dry-run",
                "--download-log",
                str(download_log),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        log_payload = json.loads(download_log.read_text(encoding="utf-8"))

        assert payload["status"] == "DISABLED"
        assert payload["writes_primary_data"] is False
        assert log_payload["entries"][0]["status"] == "DISABLED"


def test_cli_rejects_malformed_dates():
    result = subprocess.run(
        [
            "python3",
            str(PROJECT_ROOT / "scripts" / "download_chirps_direct.py"),
            "--dry-run",
            "--start-date",
            "2024-99-99",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "YYYY-MM-DD" in result.stderr
