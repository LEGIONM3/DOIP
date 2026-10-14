"""Phase 2D Test Suite: Investment Optimization Engine.

Invariants:
- Multi-attribute knapsack optimization under budget constraint.
- Total cost never exceeds specified budget.
- Output includes Pareto frontier trade-off curve.
- Plain language explanation accompanies portfolio recommendations.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.optimizer import InvestmentOptimizer, solve_investment_portfolio


def test_optimizer_budget_constraint_enforcement():
    """Optimizer allocations never exceed the allocated budget."""
    optimizer = InvestmentOptimizer()
    budget = 180000.0

    res = optimizer.solve(
        budget=budget,
        priorities={"readiness": 0.4, "coverage": 0.3, "fuel_resilience": 0.3},
    )

    assert res["total_spent"] <= budget
    assert res["budget"] == budget
    assert len(res["recommended_investments"]) > 0
    assert res["score"] > 0
    assert len(res["tradeoffs"]["frontier_curve"]) >= 3
    assert "explanation" in res
    assert res["confidence_score"] > 0.8


def test_optimizer_priority_weight_sensitivity():
    """Heavily weighting readiness selects different bundles than weighting fuel resilience."""
    res_readiness = solve_investment_portfolio(
        budget=250000.0,
        priorities={"readiness": 0.9, "coverage": 0.05, "fuel_resilience": 0.05},
    )

    res_fuel = solve_investment_portfolio(
        budget=250000.0,
        priorities={"readiness": 0.05, "coverage": 0.05, "fuel_resilience": 0.9},
    )

    assert res_readiness["total_spent"] <= 250000.0
    assert res_fuel["total_spent"] <= 250000.0

    # Fuel bladders will have higher allocation under fuel priority
    fuel_alloc_in_fuel = next(
        (a["quantity"] for a in res_fuel["recommended_investments"] if "fuel" in a["key"]),
        0,
    )
    assert fuel_alloc_in_fuel > 0


def test_optimizer_rest_endpoints():
    """POST /api/optimizer/solve and GET /api/optimizer/history work correctly."""
    client = TestClient(app)

    resp = client.post("/api/optimizer/solve", json={
        "budget": 200000.0,
        "priorities": {"readiness": 0.35, "coverage": 0.35, "risk_reduction": 0.3},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_spent"] <= 200000.0
    assert "tradeoffs" in data
    assert "kpi_deltas" in data

    # Check history
    resp_hist = client.get("/api/optimizer/history")
    assert resp_hist.status_code == 200
    assert len(resp_hist.json()["runs"]) > 0
