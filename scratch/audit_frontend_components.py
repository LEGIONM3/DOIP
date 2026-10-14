"""Hostile Audit: Level 15, 16, 17, 18 - Frontend Component & Integration Audit."""

import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List

# Backend registered endpoints (from Level 4 audit)
with open("docs/verification/api_audit.json", "r", encoding="utf-8") as fp:
    api_audit_data = json.load(fp)

backend_routes = set(r["raw_path"] for r in api_audit_data.get("routes", []))


def audit_frontend() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 15 & 16] Frontend Component & Integration Reality Audit ---")
    routes_dir = Path("src/routes")
    components_dir = Path("src/components")
    services_dir = Path("src/services")

    route_files = list(routes_dir.glob("*.tsx"))
    component_files = list(components_dir.glob("**/*.tsx"))
    service_files = list(services_dir.glob("*.ts"))

    service_audits = []
    service_endpoints = []
    api_pattern = re.compile(r'[`\'"](/api/[^`\'"?]+)[`\'"?]')
    mock_pattern = re.compile(r'\b(MOCK_|mockData|mockScenarios|dummyData|fallbackData)\b', re.IGNORECASE)

    for sf in service_files:
        if sf.name.endswith(".test.ts"):
            continue
        content = sf.read_text(encoding="utf-8")
        eps = list(set(api_pattern.findall(content)))
        service_endpoints.extend(eps)
        service_audits.append({
            "service": sf.name,
            "endpoints": eps,
            "lines": len(content.splitlines()),
        })

    # Map service name to endpoints
    service_map = {sf.stem: sf_eps for sf, sf_eps in zip(service_files, [s["endpoints"] for s in service_audits])}

    route_audits = []
    total_api_calls = 0
    matched_backend_calls = 0
    unmatched_calls = []
    mock_detected_pages = []

    for rf in route_files:
        content = rf.read_text(encoding="utf-8")
        route_name = rf.stem
        
        # 1. Detect direct API endpoints called in component
        calls = list(set(api_pattern.findall(content)))
        
        # 2. Detect imported services
        service_import_pattern = re.compile(r'from\s+[`\'"].*?/services/([a-zA-Z0-9_-]+)[`\'"]')
        for s_match in service_import_pattern.finditer(content):
            s_name = s_match.group(1)
            if s_name in service_map:
                calls.extend(service_map[s_name])
        calls = list(set(calls))
        total_api_calls += len(calls)

        # Check matched against backend
        matched = []
        unmatched = []
        for c in calls:
            # Check direct match or parameterized match
            is_match = any(
                c == br or br.startswith(c) or c.split("/")[2] == br.split("/")[2]
                for br in backend_routes if len(br.split("/")) > 2 and len(c.split("/")) > 2
            )
            if is_match:
                matched.append(c)
                matched_backend_calls += 1
            else:
                unmatched.append(c)
                unmatched_calls.append({"route": route_name, "endpoint": c})

        # 2. Detect Mock / Hardcoded Data
        has_mock = bool(mock_pattern.search(content))
        if has_mock:
            mock_detected_pages.append(route_name)

        # 3. Detect UI elements (charts, tables, modals, dialogs)
        has_table = "<table" in content or "Table" in content
        has_modal = "Dialog" in content or "Modal" in content
        has_chart = "Chart" in content or "ResponsiveContainer" in content or "svg" in content
        has_form = "<form" in content or "input" in content or "Input" in content

        # Classification
        if len(calls) == 0 and has_mock:
            status = "MOCKED_NO_BACKEND"
        elif len(unmatched) > 0 and len(matched) == 0:
            status = "DISCONNECTED_API"
        elif len(matched) > 0 and has_mock:
            status = "HYBRID_WITH_FALLBACK_MOCK"
        elif len(matched) > 0:
            status = "REAL_API_CONNECTED"
        else:
            status = "STATIC_VIEW"

        route_audits.append({
            "route_name": route_name,
            "file": rf.name,
            "status": status,
            "api_calls": calls,
            "matched_apis": matched,
            "unmatched_apis": unmatched,
            "has_mock_data": has_mock,
            "has_table": has_table,
            "has_modal": has_modal,
            "has_chart": has_chart,
            "has_form": has_form,
        })

    print(f"Total Routes Audited: {len(route_files)}")
    print(f"Total Component Files: {len(component_files)}")
    print(f"Total Frontend API Calls Identified: {total_api_calls}")
    print(f"Calls Matching Live Backend: {matched_backend_calls}")
    print(f"Pages with Mock / Fallback Data: {len(mock_detected_pages)} ({mock_detected_pages})")

    # Generate FRONTEND_COMPONENT_MATRIX.md
    out_md = Path("docs/verification/FRONTEND_COMPONENT_MATRIX.md")
    with open(out_md, "w", encoding="utf-8") as fp:
        fp.write("# DOIP Frontend Component & Route Reality Matrix\n\n")
        fp.write(f"**Total Page Routes Audited**: {len(route_files)}  \n")
        fp.write(f"**Total Subcomponents**: {len(component_files)}  \n")
        fp.write(f"**API Connections Found**: {total_api_calls}  \n\n")
        fp.write("## Route Audit Table\n\n")
        fp.write("| Route | Status | APIs Called | Matched Backend | Mock Data? | Table | Modal | Chart |\n")
        fp.write("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for ra in route_audits:
            fp.write(f"| `{ra['route_name']}` | **{ra['status']}** | {len(ra['api_calls'])} | {len(ra['matched_apis'])} | {'YES' if ra['has_mock_data'] else 'NO'} | {'✓' if ra['has_table'] else '-'} | {'✓' if ra['has_modal'] else '-'} | {'✓' if ra['has_chart'] else '-'} |\n")

    return {
        "routes_count": len(route_files),
        "components_count": len(component_files),
        "total_api_calls": total_api_calls,
        "matched_calls": matched_backend_calls,
        "unmatched_calls": unmatched_calls,
        "mock_detected_pages": mock_detected_pages,
        "route_audits": route_audits,
    }


if __name__ == "__main__":
    res = audit_frontend()
    out_json = Path("docs/verification/frontend_audit.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(res, fp, indent=2)
    print(f"Artifacts saved to {out_json} and docs/verification/FRONTEND_COMPONENT_MATRIX.md")
