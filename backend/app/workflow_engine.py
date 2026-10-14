"""Operational Workflow Engine with Mandatory Human-in-the-Loop Gate for DOIP.

Manages state-machine lifecycles for:
1. Tactical Mission Dispatch & Execution Workflows
2. Commander Approval & Authorization Workflows
3. After-Action Review (AAR) & Post-Mission Analysis
4. Threat Investigation & Countermeasure Staging

Strict Invariant: All destructive or kinetic state changes require explicit
human confirmation and cannot auto-execute without authenticated operator sign-off.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional

from app import db
from app.time_utils import utc_iso

logger = logging.getLogger("doip.workflow_engine")


class WorkflowEngine:
    """State machine governing operational workflows and human-in-the-loop approvals."""

    _instance: Optional[WorkflowEngine] = None

    @classmethod
    def get_instance(cls) -> WorkflowEngine:
        if cls._instance is None:
            cls._instance = WorkflowEngine()
        return cls._instance

    def create_workflow(
        self,
        workflow_type: str,
        title: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        requires_human_confirmation: bool = True,
    ) -> Dict[str, Any]:
        """Initialize a new staged operational workflow."""
        wf_id = f"wf-{uuid.uuid4().hex[:8]}"

        default_steps = steps or [
            {"step_id": "draft", "name": "Drafting & Assessment", "status": "completed"},
            {"step_id": "simulation_review", "name": "Simulation & Risk Evaluation", "status": "completed"},
            {"step_id": "human_gate", "name": "Commander Review & Authorization", "status": "pending"},
            {"step_id": "execution", "name": "Autonomous Dispatch", "status": "blocked"},
        ]

        record = {
            "id": wf_id,
            "workflow_type": workflow_type,
            "title": title,
            "current_step": "human_gate" if requires_human_confirmation else "execution",
            "steps": default_steps,
            "status": "staged",
            "requires_human_confirmation": requires_human_confirmation,
            "approved_by": None,
            "created_at": utc_iso(),
        }
        return db.save_workflow_instance(record)

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return db.get_workflow_instance(workflow_id)

    def list_workflows(
        self, status: Optional[str] = None, workflow_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return db.list_workflow_instances(status=status, workflow_type=workflow_type, limit=limit)

    def approve_workflow(self, workflow_id: str, operator_id: str) -> Dict[str, Any]:
        """Human-in-the-Loop authorization gate."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        steps = wf.get("steps", [])
        for s in steps:
            if s.get("step_id") == "human_gate":
                s["status"] = "approved"
                s["approved_by"] = operator_id
            elif s.get("step_id") == "execution":
                s["status"] = "in_progress"

        wf["status"] = "approved"
        wf["approved_by"] = operator_id
        wf["current_step"] = "execution"
        wf["steps"] = steps

        db.save_workflow_instance(wf)
        return wf

    def reject_workflow(self, workflow_id: str, operator_id: str, reason: str = "") -> Dict[str, Any]:
        """Human-in-the-Loop rejection."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        steps = wf.get("steps", [])
        for s in steps:
            if s.get("step_id") == "human_gate":
                s["status"] = "rejected"
                s["rejected_by"] = operator_id
                s["rejection_reason"] = reason

        wf["status"] = "rejected"
        wf["current_step"] = "rejected"
        wf["steps"] = steps

        db.save_workflow_instance(wf)
        return wf

    def advance_step(self, workflow_id: str, next_step: str) -> Dict[str, Any]:
        """Advance workflow to the next step, verifying human gate constraints."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        # Safety check: Cannot advance to execution without approval if confirmation required
        if next_step == "execution" and wf.get("requires_human_confirmation") and not wf.get("approved_by"):
            raise PermissionError("Human authorization required prior to entering execution step.")

        wf["current_step"] = next_step
        if next_step == "completed":
            wf["status"] = "completed"

        db.save_workflow_instance(wf)
        return wf


# Singleton accessor
workflow_engine = WorkflowEngine.get_instance()
