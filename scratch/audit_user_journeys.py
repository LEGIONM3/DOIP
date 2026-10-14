"""Hostile Audit: Level 17 & 18 - Complete User Journey End-to-End Execution Audit."""

import os
import sys
import json
import time
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
headers = {"X-DOIP-User": "admin"}


def run_journey(name: str, steps: list) -> Dict[str, Any]:
    print(f"\n--- Testing User Journey: {name} ---")
    step_results = []
    journey_success = True
    total_time_ms = 0.0

    for step_name, method, url, payload in steps:
        t0 = time.perf_counter()
        try:
            if method == "GET":
                resp = client.get(url, headers=headers)
            elif method == "POST":
                resp = client.post(url, headers=headers, json=payload)
            elif method == "PUT":
                resp = client.put(url, headers=headers, json=payload)
            else:
                resp = None

            dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            total_time_ms += dt_ms
            status = resp.status_code if resp else 0
            ok = status in [200, 201, 202, 204]

            if not ok:
                journey_success = False

            step_results.append({
                "step": step_name,
                "method": method,
                "url": url,
                "status_code": status,
                "latency_ms": dt_ms,
                "success": ok,
                "response_preview": str(resp.json())[:150] if ok and resp else resp.text[:150],
            })
            print(f"  [{'PASS' if ok else 'FAIL'}] {step_name} -> HTTP {status} ({dt_ms} ms)")
        except Exception as ex:
            journey_success = False
            step_results.append({
                "step": step_name,
                "method": method,
                "url": url,
                "status_code": 500,
                "success": False,
                "error": str(ex),
            })
            print(f"  [ERROR] {step_name} -> Exception: {ex}")

    return {
        "journey_name": name,
        "journey_success": journey_success,
        "total_latency_ms": round(total_time_ms, 2),
        "steps": step_results,
    }


def main():
    print("=== [DOIP LEVEL 17 & 18] User Journey Execution Audit ===")

    journeys = [
        # 1. Mission Planning
        (
            "Mission Planning",
            [
                ("AI Draft Mission", "POST", "/api/missions/ai-draft", {"intent": "Surveillance Patrol Sector Delta", "theater": "EASTERN_BORDER"}),
                ("List Missions", "GET", "/api/missions", None),
                ("Run Tactical Route Optimizer", "POST", "/api/optimizer/solve", {"start_coords": [12.97, 77.59], "target_coords": [13.05, 77.65], "threat_avoidance": True}),
            ]
        ),
        # 2. War Room
        (
            "War Room",
            [
                ("Register Presence", "POST", "/api/warroom/presence", {"callsign": "EAGLE-LEADER", "role": "OPERATOR", "sector": "SECTOR-A"}),
                ("List Active Participants", "GET", "/api/warroom/presence", None),
                ("Post Message", "POST", "/api/warroom/messages", {"content": "UAV Contact confirmed grid 44-B", "sender": "EAGLE-LEADER", "channel": "TACTICAL"}),
                ("Fetch Message Feed", "GET", "/api/warroom/messages", None),
            ]
        ),
        # 3. What-If
        (
            "What-If Analysis",
            [
                ("Run Deterministic What-If", "POST", "/api/whatif/run", {"ticks": 5, "dt_sec": 1.0, "permutations": 3}),
                ("Run Massive 100-Branch Hybrid", "POST", "/api/simulation/hybrid/whatif/massive", {"branches": 100, "ticks": 10}),
            ]
        ),
        # 4. Forecasting
        (
            "Forecasting Intelligence",
            [
                ("Generate Trajectory Forecast", "POST", "/api/forecast", {"horizon_hours": 2.0, "confidence": 0.95}),
                ("Fetch Forecast History", "GET", "/api/forecast/history", None),
            ]
        ),
        # 5. Knowledge Search & RAG
        (
            "Knowledge Search & RAG",
            [
                ("Query RAG Intelligence", "POST", "/api/ai/query", {"query": "What are emergency fuel procedures?"}),
                ("Query Knowledge Graph Entities", "GET", "/api/knowledge/graph", None),
            ]
        ),
        # 6. Analytics Center
        (
            "Analytics Center",
            [
                ("Get Operational Platform Metrics", "GET", "/api/analytics/platform", None),
                ("Get Readiness Scorecard", "GET", "/api/quality/scorecard", None),
            ]
        ),
        # 7. Simulation Replay
        (
            "Simulation Replay & AAR",
            [
                ("List Available Runs", "GET", "/api/runs", None),
                ("Get Replay Turning Points", "GET", "/api/replay/RUN-DEFAULT/turning-points", None),
            ]
        ),
        # 8. Model Lab
        (
            "Model Lab",
            [
                ("Check Laya Engine Status", "GET", "/api/laya/status", None),
                ("List Model Registry Models", "GET", "/api/laya/models", None),
                ("Run Calibrated Hybrid Step", "POST", "/api/simulation/hybrid/step", {"dt_sec": 1.0, "mode": "HYBRID_AI_SIM"}),
                ("Fetch Disagreements Log", "GET", "/api/simulation/disagreements/history?limit=10", None),
            ]
        ),
        # 9. Digital Twin & Multiworld
        (
            "Digital Twin & Multiworld",
            [
                ("Generate Multiworld Futures", "POST", "/api/futures/generate", {"count": 4, "base_state": {"tick": 0}}),
                ("Fetch Federation Status", "GET", "/api/federation/theaters", None),
            ]
        ),
    ]

    all_results = []
    passed_journeys = 0

    for j_name, j_steps in journeys:
        res = run_journey(j_name, j_steps)
        all_results.append(res)
        if res["journey_success"]:
            passed_journeys += 1

    print("\n=======================================================")
    print(f"User Journeys Summary: {passed_journeys} / {len(journeys)} Journeys Fully Passed")
    print("=======================================================")

    out_file = Path("docs/verification/user_journeys_audit.json")
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump({
            "total_journeys": len(journeys),
            "passed_journeys": passed_journeys,
            "journeys": all_results,
        }, fp, indent=2)
    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    main()
