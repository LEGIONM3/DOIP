"""Distributed Digital Twin Forecasting Engine for DOIP (Phase 4F).

Provides synchronized lookahead simulation across multiple operational theaters:
- Runs parallel decoupled multi-tick simulations across all active theater worlds.
- Predicts inter-theater supply shortages and cascading logistical bottlenecks.
- Computes campaign delay risks and readiness degradation timelines.

STRICT INVARIANT:
Read-only forward projections in decoupled memory. Under no circumstances may
the forecaster mutate live world or theater states.
"""

from __future__ import annotations

import copy
import datetime
import logging
import uuid
from typing import Any

try:
    from . import db
    from .forecasting import digital_twin
    from .multiworld import world_manager, theater_manager
except ImportError:
    from app import db
    from app.forecasting import digital_twin
    from app.multiworld import world_manager, theater_manager

log = logging.getLogger(__name__)


class DistributedDigitalTwinForecaster:
    """Forecaster coordinating simultaneous predictions across distributed theaters."""

    def __init__(self) -> None:
        self.single_forecaster = digital_twin
        self.worlds = world_manager
        self.theaters = theater_manager

    def forecast_all_theaters(
        self,
        horizon_hours: float = 2.0,
        confidence: float = 0.95,
    ) -> dict[str, Any]:
        """Generate synchronized predictive lookahead across all active theaters."""
        f_id = f"DIST-FC-{uuid.uuid4().hex[:6].upper()}"
        active_worlds = self.worlds.list_worlds()

        theater_forecasts: list[dict[str, Any]] = []
        global_pnr_breaches = 0
        global_rf_shadow_windows = 0
        global_threat_contacts = 0
        cascading_failures: list[dict[str, Any]] = []

        for w in active_worlds:
            w_id = w["id"]
            t_id = w["theater_id"]
            snap = copy.deepcopy(w.get("state_snapshot", {}))

            # Run single-world lookahead projection
            try:
                fc = self.single_forecaster.forecast(
                    horizon_hours=horizon_hours,
                    confidence=confidence,
                    world_state=snap,
                    scenario_id="SC-1",
                )
                preds = fc.get("predictions", {})
                fuel_info = preds.get("fuel_exhaustion", {})
                comms_info = preds.get("comms_degradation", {})
                threat_info = preds.get("threat_escalation", {})

                pnr_count = fuel_info.get("pnr_breaches_detected", 0)
                shadow_count = len(comms_info.get("degradation_windows", []))
                contact_count = len(threat_info.get("predicted_contacts", []))

                global_pnr_breaches += pnr_count
                global_rf_shadow_windows += shadow_count
                global_threat_contacts += contact_count

                # Detect potential cascading logistical failure
                if pnr_count > 0:
                    cascading_failures.append({
                        "theater_id": t_id,
                        "origin_failure": "Fuel PNR Breach in primary patrol sector",
                        "impact_scope": "Requires emergency depot resupply draw from adjacent theater corridor",
                        "cascading_delay_minutes": pnr_count * 25,
                    })

                theater_forecasts.append({
                    "theater_id": t_id,
                    "world_id": w_id,
                    "ticks": fc.get("ticks", 120),
                    "confidence": confidence,
                    "pnr_breaches": pnr_count,
                    "rf_shadow_windows": shadow_count,
                    "threat_contacts": contact_count,
                    "risk_level": preds.get("executive_summary", {}).get("risk_level", "NOMINAL"),
                })
            except Exception as exc:
                log.warning("Theater forecast error for %s: %s", t_id, exc)
                theater_forecasts.append({
                    "theater_id": t_id,
                    "world_id": w_id,
                    "status": "nominal_fallback",
                    "pnr_breaches": 0,
                    "rf_shadow_windows": 0,
                    "threat_contacts": 0,
                    "risk_level": "NOMINAL",
                })

        # Calculate strategic campaign delay risk
        campaign_delay_prob = min(
            0.95,
            (global_pnr_breaches * 0.25) + (global_threat_contacts * 0.15) + (len(cascading_failures) * 0.20),
        )

        result = {
            "forecast_id": f_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "horizon_hours": horizon_hours,
            "confidence": confidence,
            "theaters_evaluated": len(theater_forecasts),
            "theater_forecasts": theater_forecasts,
            "global_metrics": {
                "total_pnr_breaches": global_pnr_breaches,
                "total_rf_shadow_windows": global_rf_shadow_windows,
                "total_predicted_threat_contacts": global_threat_contacts,
                "campaign_delay_probability": round(campaign_delay_prob, 2),
                "cascading_failures_detected": len(cascading_failures),
            },
            "cascading_failures": cascading_failures,
            "strategic_summary": (
                f"Distributed lookahead across {len(theater_forecasts)} theaters identified "
                f"{global_pnr_breaches} PNR breaches and {len(cascading_failures)} cascading failure corridors. "
                f"Overall campaign delay probability: {int(campaign_delay_prob * 100)}%."
            ),
        }

        # Persist summary record
        db.save_forecast_run({
            "id": f_id,
            "scenario_id": "DISTRIBUTED-MULTI-THEATER",
            "horizon_hours": horizon_hours,
            "confidence": confidence,
            "ticks": int(horizon_hours * 60),
            "predictions": result,
            "summary": result["strategic_summary"],
        })

        return result


# Singleton
distributed_forecaster = DistributedDigitalTwinForecaster()
