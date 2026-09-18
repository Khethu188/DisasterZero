"""
src/reporting/report_generator.py
Generates disaster recovery incident reports.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class IncidentReport:
    incident_id: str = ""
    scenario_name: str = ""
    overall_passed: bool = False
    detection: Any = None
    recovery: Any = None
    rto_rpo: Any = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.incident_id:
            self.incident_id = "INC-" + uuid.uuid4().hex[:8].upper()


class RecoveryReportGenerator:
    """Generate disaster recovery reports."""

    def __init__(self, config_or_dir=None):
        if config_or_dir is None:
            self.reports_dir = "reports"
        elif isinstance(config_or_dir, str):
            self.reports_dir = config_or_dir
        else:
            # It is a config object
            self.config = config_or_dir
            self.reports_dir = "reports"
        os.makedirs(self.reports_dir, exist_ok=True)

    def build_incident_report(
        self,
        scenario_name: str,
        detection: Any,
        recovery: Any,
        rto_rpo: Any,
    ) -> IncidentReport:
        """Build an incident report from scenario results."""
        report = IncidentReport(
            scenario_name=scenario_name,
            overall_passed=rto_rpo.verification_passed if rto_rpo else False,
            detection=detection,
            recovery=recovery,
            rto_rpo=rto_rpo,
        )
        self._save_report(report)
        return report

    def generate_json(self, rto_rpo_report) -> Dict[str, Any]:
        """Generate a JSON-serializable report dict."""
        return {
            "incident_id": getattr(rto_rpo_report, "incident_id", ""),
            "failure_type": getattr(rto_rpo_report, "failure_type", ""),
            "target": getattr(rto_rpo_report, "target", ""),
            "rto": {
                "detection_time_seconds": getattr(rto_rpo_report, "detection_time_seconds", 0),
                "recovery_time_seconds": getattr(rto_rpo_report, "recovery_time_seconds", 0),
                "total_rto_seconds": getattr(rto_rpo_report, "total_rto_seconds", 0),
                "target_seconds": getattr(rto_rpo_report, "rto_target_seconds", 0),
                "met": getattr(rto_rpo_report, "rto_met", False),
            },
            "rpo": {
                "records_recovered": getattr(rto_rpo_report, "records_after_recovery", 0),
                "records_lost": getattr(rto_rpo_report, "records_lost", 0),
                "target_records": getattr(rto_rpo_report, "rpo_target_records", 0),
                "met": getattr(rto_rpo_report, "rpo_met", False),
            },
            "verification_passed": getattr(rto_rpo_report, "verification_passed", False),
        }

    def _save_report(self, report: IncidentReport) -> str:
        """Save report to JSON file."""
        try:
            filepath = os.path.join(
                self.reports_dir,
                f"incident_{report.incident_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            )
            data = {
                "incident_id": report.incident_id,
                "scenario_name": report.scenario_name,
                "overall_passed": report.overall_passed,
                "created_at": str(report.created_at),
            }
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return filepath
        except Exception:
            return ""
