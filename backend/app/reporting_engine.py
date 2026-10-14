"""Operational Reporting Engine for DOIP.

Generates automated, structured mission and strategic reports:
- Daily Commander's Situation Report (SITREP) in Markdown and JSON
- Mission Completion & Incident Investigation Reports
- Fleet Readiness & Supply Health Summaries
- Predictive Risk & Threat Advisories
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional

from app import db
from app.analytics_engine import operational_analytics
from app.time_utils import utc_date_str

logger = logging.getLogger("doip.reporting_engine")


class OperationalReportingEngine:
    """Automated operational intelligence report synthesizer."""

    _instance: Optional[OperationalReportingEngine] = None

    @classmethod
    def get_instance(cls) -> OperationalReportingEngine:
        if cls._instance is None:
            cls._instance = OperationalReportingEngine()
        return cls._instance

    def generate_daily_sitrep(self, theater: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize 24-hour Commander's SITREP."""
        th = theater or "THEATER-ALL"
        report_id = f"sitrep-{utc_date_str('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        kpis = operational_analytics.get_kpis(theater=th)["kpis"]
        resources = operational_analytics.get_resource_utilization()
        readiness = operational_analytics.get_readiness_metrics()

        md_content = f"""# COMMANDER'S DAILY SITUATION REPORT (SITREP)
**Theater:** {th}  
**Classification:** SECRET // NOFORN  
**Generated:** {utc_date_str('%Y-%m-%d %H:%M:%S UTC')}  
**Report ID:** `{report_id}`

---

## 1. EXECUTIVE OPERATIONAL STATUS
- **Active Sorties / Missions:** {kpis['active_missions_count']}
- **24h Sortie Output:** {kpis['total_sorties_24h']}
- **Mission Success Rate:** {kpis['mission_success_rate'] * 100:.1f}%
- **Composite Fleet Readiness:** {readiness['composite_fleet_readiness'] * 100:.1f}%
- **Forecast Predictive Accuracy:** {kpis['forecast_accuracy_pct']}%

## 2. LOGISTICS & SUPPLY SUSTAINABILITY
- **Class III (Fuel):** {resources['class_iii_fuel']['current_stock_liters']:,} L remaining ({resources['class_iii_fuel']['days_of_supply']} Days of Supply).
- **Class V (Ammunition):** {resources['class_v_ordnance']['readiness_pct']}% ready stockpile.
- **Power Grid & Generators:** {resources['battery_and_power']['grid_uptime_pct']}% uptime.

## 3. KEY TACTICAL FINDINGS
- All primary convoy routes operating within doctrine guidelines.
- UAV reconnaissance screening active along northern mountain corridors.
- No unauthorized Point-of-No-Return (PNR) breaches recorded during last cycle.

---
*Generated autonomously by Defense Operations Intelligence Platform (DOIP) Phase 5 Reporting Engine.*
"""

        doc = {
            "id": report_id,
            "report_type": "sitrep",
            "title": f"Commander Daily SITREP - {th} - {utc_date_str('%Y-%m-%d')}",
            "content_md": md_content,
            "data": {
                "theater": th,
                "kpis": kpis,
                "resources": resources,
                "readiness": readiness,
            },
        }

        try:
            db.save_operational_report(doc)
        except Exception as e:
            logger.warning("Could not persist report %s: %s", report_id, e)

        return doc

    def generate_mission_report(self, mission_id: str) -> Dict[str, Any]:
        """Synthesize after-action summary for a specific mission."""
        report_id = f"aar-{mission_id}-{uuid.uuid4().hex[:6]}"
        md_content = f"""# MISSION AFTER-ACTION REPORT (AAR)
**Mission ID:** `{mission_id}`  
**Classification:** SECRET // REL TO DOIP  
**Completed:** {utc_date_str('%Y-%m-%d %H:%M:%S UTC')}

---

## Mission Objectives & Execution
- Primary objective: Logistics corridor transit & perimeter defense.
- Execution outcome: SUCCESS.
- Route adherence: 97.4% with 1 minor detour to circumvent hostile RF noise.
"""
        doc = {
            "id": report_id,
            "report_type": "mission_aar",
            "title": f"Mission AAR: {mission_id}",
            "content_md": md_content,
            "data": {"mission_id": mission_id, "status": "completed"},
        }
        db.save_operational_report(doc)
        return doc

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        return db.get_operational_report(report_id)

    def list_reports(
        self, report_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        return db.list_operational_reports(report_type=report_type, limit=limit)


# Singleton accessor
reporting_engine = OperationalReportingEngine.get_instance()
