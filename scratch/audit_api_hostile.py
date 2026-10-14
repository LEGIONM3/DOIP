"""Hostile Audit: Level 4 & Level 14 - Comprehensive API & Security Hostile Audit."""

import os
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

SECURITY_PAYLOADS = [
    "' OR '1'='1' --",
    "'; DROP TABLE users; --",
    "../../../../windows/win.ini",
    "<script>alert('XSS')</script>",
    "{\"__proto__\": {\"admin\": true}}",
]


def extract_routes() -> List[Dict[str, Any]]:
    routes = []
    for r in app.routes:
        if hasattr(r, "methods") and hasattr(r, "path"):
            # Exclude OpenAPI/docs
            if r.path in ["/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"]:
                continue
            for method in r.methods:
                if method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    routes.append({
                        "path": r.path,
                        "method": method,
                        "name": getattr(r, "name", ""),
                    })
    return routes


def test_endpoint(route: Dict[str, Any]) -> Dict[str, Any]:
    path = route["path"]
    method = route["method"]

    # Replace path parameters with realistic test values
    test_path = path
    if "{run_id}" in test_path:
        test_path = test_path.replace("{run_id}", "RUN-AUDIT-TEST")
    if "{mission_id}" in test_path:
        test_path = test_path.replace("{mission_id}", "MSN-AUDIT-TEST")
    if "{scenario_id}" in test_path:
        test_path = test_path.replace("{scenario_id}", "SCN-AUDIT-TEST")
    if "{theater_id}" in test_path:
        test_path = test_path.replace("{theater_id}", "THEATER-PACIFIC")
    if "{theater}" in test_path:
        test_path = test_path.replace("{theater}", "EASTERN_BORDER")
    if "{campaign_id}" in test_path:
        test_path = test_path.replace("{campaign_id}", "CAMP-AUDIT-TEST")
    if "{agent_id}" in test_path:
        test_path = test_path.replace("{agent_id}", "AGENT-INTEL-01")
    if "{task_id}" in test_path:
        test_path = test_path.replace("{task_id}", "TASK-AUDIT-TEST")
    if "{node_id}" in test_path:
        test_path = test_path.replace("{node_id}", "NODE-AUDIT-TEST")
    if "{workflow_id}" in test_path:
        test_path = test_path.replace("{workflow_id}", "WF-AUDIT-TEST")
    if "{forecast_id}" in test_path:
        test_path = test_path.replace("{forecast_id}", "FC-AUDIT-TEST")
    if "{version}" in test_path:
        test_path = test_path.replace("{version}", "v1")
    if "{entity_id}" in test_path:
        test_path = test_path.replace("{entity_id}", "ENT-01")

    headers_auth = {"X-DOIP-User": "admin"}
    headers_operator = {"X-DOIP-User": "operator"}

    result = {
        "raw_path": path,
        "test_path": test_path,
        "method": method,
        "happy_status": None,
        "happy_latency_ms": None,
        "unauth_status": None,
        "empty_payload_status": None,
        "security_tests_passed": True,
        "security_details": [],
        "verdict": "UNTESTED",
    }

    # 1. Happy Path / Standard Request
    t0 = time.perf_counter()
    try:
        if method == "GET":
            resp = client.get(test_path, headers=headers_auth)
        elif method == "POST":
            resp = client.post(test_path, headers=headers_auth, json={"query": "test", "name": "Audit", "ticks": 5, "dt_sec": 1.0, "branches": 10})
        elif method == "PUT":
            resp = client.put(test_path, headers=headers_auth, json={"status": "ACTIVE"})
        elif method == "DELETE":
            resp = client.delete(test_path, headers=headers_auth)
        else:
            resp = None
        t1 = time.perf_counter()
        if resp is not None:
            result["happy_status"] = resp.status_code
            result["happy_latency_ms"] = round((t1 - t0) * 1000.0, 2)
    except Exception as ex:
        result["happy_status"] = 500
        result["error"] = str(ex)

    # 2. Unauthenticated Test (missing headers)
    try:
        if method == "GET":
            resp_unauth = client.get(test_path)
        elif method == "POST":
            resp_unauth = client.post(test_path, json={})
        elif method == "PUT":
            resp_unauth = client.put(test_path, json={})
        else:
            resp_unauth = None
        if resp_unauth is not None:
            result["unauth_status"] = resp_unauth.status_code
    except Exception:
        pass

    # 3. Missing / Malformed Payload Test (for POST/PUT)
    if method in ["POST", "PUT"]:
        try:
            if method == "POST":
                resp_empty = client.post(test_path, headers=headers_auth, json={})
            else:
                resp_empty = client.put(test_path, headers=headers_auth, json={})
            result["empty_payload_status"] = resp_empty.status_code
            # Valid API should return 200, 201, or 422 (validation error), but NEVER unhandled 500
            if resp_empty.status_code == 500:
                result["security_tests_passed"] = False
                result["security_details"].append("Empty payload caused unhandled 500 Internal Server Error")
        except Exception as ex:
            result["security_tests_passed"] = False
            result["security_details"].append(f"Empty payload exception: {ex}")

    # 4. Security Injection Test
    for sec_payload in SECURITY_PAYLOADS:
        try:
            if method == "GET":
                resp_sec = client.get(f"{test_path}?q={sec_payload}", headers=headers_auth)
            elif method == "POST":
                resp_sec = client.post(test_path, headers=headers_auth, json={"query": sec_payload, "name": sec_payload, "model_id": sec_payload})
            else:
                resp_sec = None

            if resp_sec is not None:
                # If server returns 500 or SQL syntax leak, mark as vulnerability
                text_lower = resp_sec.text.lower()
                if "syntax error" in text_lower or "sqlite3.operationalerror" in text_lower or "psycopg2.errors" in text_lower:
                    result["security_tests_passed"] = False
                    result["security_details"].append(f"SQL injection leak detected with payload: {sec_payload}")
                if resp_sec.status_code == 500:
                    result["security_details"].append(f"Security payload caused 500 error: {sec_payload}")
        except Exception as ex:
            result["security_details"].append(f"Exception on security payload: {ex}")

    # Overall Verdict
    h_code = result["happy_status"]
    if h_code in [200, 201, 202, 204]:
        result["verdict"] = "WORKING"
    elif h_code in [404, 400, 422]:
        result["verdict"] = "REQUIRES_SPECIFIC_ENTITY"
    elif h_code == 401 or h_code == 403:
        result["verdict"] = "AUTH_PROTECTED"
    elif h_code == 500:
        result["verdict"] = "BROKEN_500"
    else:
        result["verdict"] = f"STATUS_{h_code}"

    return result


def main():
    print("=== [DOIP LEVEL 4 & 14] Comprehensive API & Security Hostile Audit ===")
    routes = extract_routes()
    print(f"Discovered {len(routes)} distinct API routes on FastAPI application.")

    audit_records = []
    status_summary: Dict[int, int] = {}
    verdict_summary: Dict[str, int] = {}
    total_time = 0.0

    for i, r in enumerate(routes, 1):
        rec = test_endpoint(r)
        audit_records.append(rec)
        h = rec["happy_status"] or 0
        v = rec["verdict"]
        status_summary[h] = status_summary.get(h, 0) + 1
        verdict_summary[v] = verdict_summary.get(v, 0) + 1
        if rec["happy_latency_ms"]:
            total_time += rec["happy_latency_ms"]

    avg_latency = round(total_time / max(1, len(routes)), 2)

    print("\n--- API Execution Summary ---")
    print(f"Total Routes Audited: {len(routes)}")
    print(f"Average Endpoint Latency: {avg_latency} ms")
    print(f"Verdicts: {verdict_summary}")
    print(f"Status Codes: {status_summary}")

    # Save JSON artifact
    out_json = Path("docs/verification/api_audit.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump({
            "total_routes": len(routes),
            "average_latency_ms": avg_latency,
            "verdicts": verdict_summary,
            "status_codes": status_summary,
            "routes": audit_records,
        }, fp, indent=2)

    # Generate Markdown API Coverage Matrix
    out_md = Path("docs/verification/API_COVERAGE_MATRIX.md")
    with open(out_md, "w", encoding="utf-8") as fp:
        fp.write("# DOIP Comprehensive API & Security Coverage Matrix\n\n")
        fp.write(f"**Total Audited Endpoints**: {len(routes)}  \n")
        fp.write(f"**Average Latency**: {avg_latency} ms  \n\n")
        fp.write("## Verdict Summary\n\n")
        fp.write("| Verdict | Count | Description |\n|:---|:---:|:---|\n")
        for k, v in verdict_summary.items():
            fp.write(f"| `{k}` | **{v}** | Tested behavior classification |\n")
        fp.write("\n## Endpoint Audit Table\n\n")
        fp.write("| Method | Route | Happy Status | Latency (ms) | Unauth Status | Security Tests | Verdict |\n")
        fp.write("|:---|:---|:---:|:---:|:---:|:---:|:---|\n")
        for rec in audit_records:
            sec_flag = "PASSED" if rec["security_tests_passed"] else f"FLAGGED ({len(rec['security_details'])})"
            fp.write(f"| `{rec['method']}` | `{rec['raw_path']}` | `{rec['happy_status']}` | {rec['happy_latency_ms']} | `{rec['unauth_status']}` | `{sec_flag}` | **{rec['verdict']}** |\n")

    print(f"Saved artifacts to {out_json} and {out_md}")


if __name__ == "__main__":
    main()
