"""Phase 4G Test Suite: Autonomous Simulation Branching & Future Generator.

Invariants:
- Deterministic branching: Consistent PRNG seed generation per future branch.
- Multi-tier risk bands: P10 (Optimistic), P50 (Median), P90 (Conservative), WORST.
- Live state immutability: Alternative branches are read-only and never mutate baseline state.
- Persistence to database.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.future_generator import FutureGenerator, future_generator
from app import db
import uuid


def test_future_generation_determinism():
    """Verify future generation generates identical reproducible outcomes for same seeds."""
    gen = FutureGenerator()
    res1 = gen.generate_alternative_futures(baseline_world_id="WLD-NORTH-01", count=10, ticks=60)
    res2 = gen.generate_alternative_futures(baseline_world_id="WLD-NORTH-01", count=10, ticks=60)

    # Risk band values should match deterministically
    assert res1["risk_bands"]["P10_optimistic"]["score"] == res2["risk_bands"]["P10_optimistic"]["score"]
    assert res1["risk_bands"]["P50_median"]["score"] == res2["risk_bands"]["P50_median"]["score"]
    assert res1["risk_bands"]["P90_conservative"]["score"] == res2["risk_bands"]["P90_conservative"]["score"]
    assert res1["risk_bands"]["WORST_case"]["score"] == res2["risk_bands"]["WORST_case"]["score"]


def test_future_branch_risk_bands_and_ranking():
    """Verify branches are categorized into P10, P50, P90, and WORST risk bands."""
    gen = FutureGenerator()
    test_world_id = f"WLD-FUT-{uuid.uuid4().hex[:6]}"
    result = gen.generate_alternative_futures(baseline_world_id=test_world_id, count=15, ticks=90)

    assert result["branches_count"] == 15
    assert len(result["top_branches"]) <= 5

    # Verify descending score ordering by rank in top_branches
    scores = [b["score"] for b in result["top_branches"]]
    assert scores == sorted(scores, reverse=True)

    # Check risk bands present in persisted branches
    persisted = db.list_future_branches(baseline_world_id=test_world_id, limit=20)
    assert len(persisted) == 15
    bands = {b["risk_band"] for b in persisted}
    assert "P10" in bands
    assert "P50" in bands
    assert "P90" in bands
    assert "WORST" in bands


def test_futures_rest_api_endpoints():
    """Verify FastAPI endpoints for future generation and listing."""
    client = TestClient(app)

    # 1. Generate futures
    gen_req = {
        "baseline_world_id": "WLD-NORTH-01",
        "count": 10,
        "ticks": 120,
    }
    res_gen = client.post("/api/futures/generate", json=gen_req)
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["branches_count"] == 10
    assert "risk_bands" in gen_data
    assert "P10_optimistic" in gen_data["risk_bands"]
    assert "WORST_case" in gen_data["risk_bands"]

    # 2. List futures
    res_list = client.get("/api/futures?baseline_world_id=WLD-NORTH-01&limit=20")
    assert res_list.status_code == 200
    branch_list = res_list.json()
    assert isinstance(branch_list, list)
    assert len(branch_list) >= 10
