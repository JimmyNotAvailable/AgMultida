from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from ai_serving.main import ManifestSampleStore, app


@pytest.fixture
def sample_dataset(tmp_path: Path) -> Path:
    sample_dir = tmp_path / "samples" / "A01_20240101_TEST1234"
    sample_dir.mkdir(parents=True, exist_ok=True)
    np.save(sample_dir / "image.npy", np.ones((4, 224, 224), dtype=np.float32))
    np.save(sample_dir / "sensor_seq.npy", np.ones((48, 8), dtype=np.float32))
    np.save(sample_dir / "weather_ctx.npy", np.ones((6,), dtype=np.float32))
    manifest = pd.DataFrame([
        {
            "sample_id": "A01_20240101_TEST1234",
            "zone_id": "A01",
            "timestamp_utc": "2024-01-01T03:00:00Z",
            "image_path": "samples/A01_20240101_TEST1234/image.npy",
            "sensor_seq_path": "samples/A01_20240101_TEST1234/sensor_seq.npy",
            "weather_ctx_path": "samples/A01_20240101_TEST1234/weather_ctx.npy",
            "modality_mask": "[1.0, 1.0, 1.0]",
            "source_status": "PASS",
        }
    ])
    manifest_path = tmp_path / "sample_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    return manifest_path


def test_manifest_sample_store_resolves_latest(sample_dataset: Path):
    store = ManifestSampleStore(sample_dataset)
    row = store.find_latest_sample("A01", datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc))
    assert row["sample_id"] == "A01_20240101_TEST1234"
    image, sensor_seq, weather_ctx, mask = store.assemble_inputs(row)
    assert image.shape == (1, 4, 224, 224)
    assert sensor_seq.shape == (1, 48, 8)
    assert weather_ctx.shape == (1, 6)
    assert mask.shape == (1, 3)


def test_internal_predict_requires_ready_pipeline():
    with TestClient(app) as client:
        app.state.pipeline = None
        app.state.sample_store = None
        app.state.readiness_error = "not ready"
        resp = client.post("/internal/predict", json={"zone_id": "A01", "timestamp": "2024-01-01T03:00:00Z"})
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "MODEL_NOT_FOUND"


def test_readyz_shape():
    with TestClient(app) as client:
        resp = client.get("/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "model_loaded" in body
        assert "manifest_loaded" in body
