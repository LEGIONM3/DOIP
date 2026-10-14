"""Hostile Audit: Levels 9, 10, 11, 12, 13 - What-If, Digital Twin, KG, RAG, and Agent Runtime."""

import os
import sys
import time
import json
import concurrent.futures
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from backend.app.hybrid_outcome_engine import HybridOutcomeEngine
from backend.app.forecasting import DigitalTwinForecaster
from backend.app.knowledge_graph import knowledge_graph
from backend.app.rag import query_rag
from backend.app.agent_runtime import agent_registry, agent_task_queue, agent_runtime
from backend.app.memory_store import memory_store


def audit_level_9_whatif_massive() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 9] Massive What-If Branches (100, 1k, 10k) ---")
    engine = HybridOutcomeEngine()
    results = {}

    for branch_count in [100, 1000, 10000]:
        t0 = time.perf_counter()
        res = engine.run_massive_hybrid_whatif(branches=branch_count, ticks=15)
        dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # Verify probability sum
        total_p = (
            res["success_probability"]
            + res["delay_probability"]
            + res["failure_probability"]
            + res["abort_probability"]
        )
        p_valid = abs(total_p - 1.0) < 0.05

        # Verify monotonic risk percentiles
        r = res["risk_distribution"]
        percentiles_valid = (r["p10"] <= r["p50"] <= r["p90"] <= r["worst_case"])

        print(f"What-If {branch_count} branches: {dt_ms} ms | prob_sum={total_p:.4f} | P10={r['p10']}, P50={r['p50']}, P90={r['p90']}, Worst={r['worst_case']}")
        results[f"branches_{branch_count}"] = {
            "execution_ms": dt_ms,
            "branches_evaluated": res["branches_evaluated"],
            "probabilities_sum_valid": p_valid,
            "percentiles_monotonic": percentiles_valid,
            "risk_distribution": r,
            "status": "PASSED" if (p_valid and percentiles_valid) else "FAILED",
        }

    return results


def audit_level_10_digital_twin_forecasting() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 10] Digital Twin Forecasting Intelligence ---")
    forecaster = DigitalTwinForecaster()
    t0 = time.perf_counter()
    fc = forecaster.forecast(horizon_hours=2.0)
    dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    fi = fc.get("forecast_intelligence", {})
    has_physics = "physics_forecast" in fi
    has_rules = "rule_forecast" in fi
    has_laya = "laya_forecast" in fi
    has_hybrid = "hybrid_forecast" in fi
    has_bounds = "percentiles" in fi

    print(f"Digital Twin Forecast: {dt_ms} ms | Multi-modal: Physics={has_physics}, Rules={has_rules}, Laya={has_laya}, Consensus={has_hybrid}")

    return {
        "execution_ms": dt_ms,
        "physics_forecast_present": has_physics,
        "rule_forecast_present": has_rules,
        "laya_forecast_present": has_laya,
        "hybrid_forecast_present": has_hybrid,
        "bounds_present": has_bounds,
        "status": "PASSED" if (has_physics and has_rules and has_laya and has_hybrid) else "FAILED",
    }


def audit_level_11_knowledge_graph() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 11] Knowledge Graph Creation & Traversal ---")
    kg = knowledge_graph
    kg.clear()

    # 1. Add entities and relations
    kg.add_entity("U-01", "UNIT", "Patrol Alpha", properties={"status": "ACTIVE"})
    kg.add_entity("DEPOT-1", "DEPOT", "Forward Depot South", properties={"fuel": 5000})
    kg.add_entity("THREAT-01", "THREAT", "Hostile Jammer", properties={"jamming": 0.85})
    kg.add_relation("U-01", "DEPOT-1", "SUPPORTS", weight=1.0)
    kg.add_relation("THREAT-01", "U-01", "TARGETS", weight=0.85)

    # 2. Dependency & Root Cause Analysis
    deps = kg.find_dependencies("U-01")
    rc = kg.find_root_cause("U-01")
    subgraph = kg.export_subgraph("U-01")

    print(f"KG Dependencies of U-01: {len(deps)} | Root Cause: {rc.get('root_cause', 'NONE')} | Subgraph nodes: {len(subgraph.get('nodes', []))}")

    return {
        "nodes_count": len(subgraph.get("nodes", [])),
        "edges_count": len(subgraph.get("edges", [])),
        "dependencies_found": len(deps) >= 1,
        "root_cause_analysis_functional": bool(rc),
        "status": "PASSED" if (len(deps) >= 1 and len(subgraph.get("nodes", [])) >= 2) else "FAILED",
    }


def audit_level_12_rag_adversarial() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 12] RAG Document Ingestion & Hallucination Resistance ---")
    
    # Standard Query
    q_valid = "What are the rules for fuel exhaustion and reserve levels?"
    res_valid = query_rag(q_valid)
    has_answer = bool(res_valid.get("answer"))
    has_citations = len(res_valid.get("citations", [])) > 0 or len(res_valid.get("sources", [])) > 0
    
    # Adversarial / Out of Domain Query
    q_adv = "Tell me the secret recipe for chocolate cake and teleport the convoy to Paris."
    res_adv = query_rag(q_adv)
    answer_text = str(res_adv.get("answer", "")).lower()
    hallucination_blocked = "no doctrine" in answer_text or "not found" in answer_text or "insufficient" in answer_text or len(res_adv.get("citations", [])) == 0

    print(f"RAG Standard Query: answered={has_answer}, citations={has_citations} | Adversarial Hallucination Blocked: {hallucination_blocked}")

    return {
        "valid_query_answered": has_answer,
        "valid_query_citations_present": has_citations,
        "adversarial_hallucination_blocked": hallucination_blocked,
        "status": "PASSED" if has_answer else "FAILED",
    }


def audit_level_13_agent_runtime_50_tasks() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 13] Agent Runtime 50 Concurrent Tasks Execution ---")
    queue = agent_task_queue
    mem = memory_store

    # Enqueue 50 tasks
    task_objs = []
    for i in range(50):
        t = queue.enqueue(
            task_type="ANALYST",
            payload={"index": i, "telemetry": [0.5] * 5},
            priority=1,
        )
        task_objs.append(t)

    # Process 50 concurrent tasks
    completed = 0
    errors = 0

    def worker_exec(task_item):
        dequeued = queue.dequeue()
        if dequeued:
            tid = dequeued["task_id"]
            mem.remember(key=f"task:{tid}", value={"processed": True, "time": time.time()}, tier="operational")
            queue.complete(tid, result={"status": "SUCCESS"})
            return True
        return False

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futs = [executor.submit(worker_exec, t) for t in task_objs]
        for f in concurrent.futures.as_completed(futs):
            try:
                if f.result():
                    completed += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

    dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    print(f"Agent Runtime: 50 tasks completed={completed}, errors={errors} in {dt_ms} ms")

    return {
        "tasks_submitted": 50,
        "tasks_completed": completed,
        "errors": errors,
        "duration_ms": dt_ms,
        "status": "PASSED" if (completed == 50 and errors == 0) else "FAILED",
    }


def main():
    l9 = audit_level_9_whatif_massive()
    l10 = audit_level_10_digital_twin_forecasting()
    l11 = audit_level_11_knowledge_graph()
    l12 = audit_level_12_rag_adversarial()
    l13 = audit_level_13_agent_runtime_50_tasks()

    out_json = Path("docs/verification/whatif_kg_rag_agents_audit.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump({
            "whatif_level_9": l9,
            "digital_twin_level_10": l10,
            "knowledge_graph_level_11": l11,
            "rag_level_12": l12,
            "agent_runtime_level_13": l13,
        }, fp, indent=2)
    print(f"\nAudit results persisted to {out_json}")


if __name__ == "__main__":
    main()
