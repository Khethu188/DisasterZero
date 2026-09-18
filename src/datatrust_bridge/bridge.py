
"""
src/datatrust_bridge/bridge.py
──────────────────────────────
Connects DataTrust quality gates to DisasterZero recovery.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import DisasterZeroConfig
from src.datatrust_bridge.quality_gate import (
    DataTrustQualityGate,
    QualityGateResult,
    QualityStatus,
)
from src.detector.base import DetectionResult


class DataTrustBridge:
    """Bridge between DataTrust quality checks and DisasterZero recovery."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.quality_gate = DataTrustQualityGate(config)
        self.recovery_engine = None
        self.gate_history: List[QualityGateResult] = []
        self.recovery_history: List[Dict[str, Any]] = []

    def connect_to_disasterzero(self, recovery_engine) -> None:
        """Connect a recovery engine to receive quality gate triggers."""
        self.recovery_engine = recovery_engine
        self.quality_gate.register_recovery_callback(self._on_quality_failure)

    def run_quality_gate(self, table: str) -> QualityGateResult:
        """Run quality gate on a table and handle results."""
        result = self.quality_gate.evaluate(table)
        self.gate_history.append(result)

        if result.overall_status == QualityStatus.CRITICAL and result.triggered_recovery:
            self._on_quality_failure(result)

        return result

    def run_post_transformation_gate(
        self,
        silver_table: str,
        gold_table: str,
    ) -> Dict[str, QualityGateResult]:
        """Run quality gates on both Silver and Gold layers."""
        silver_result = self.quality_gate.evaluate(silver_table)
        self.gate_history.append(silver_result)

        gold_result = self.quality_gate.evaluate(gold_table)
        self.gate_history.append(gold_result)

        return {
            "silver": silver_result,
            "gold": gold_result,
        }

    def _on_quality_failure(self, gate_result: QualityGateResult) -> None:
        """Handle a critical quality gate failure by triggering recovery."""
        if self.recovery_engine is None:
            return

        # Convert quality failure to a detection result
        detection = DetectionResult(
            detected=True,
            failure_type="data_corruption",
            target=gate_result.table or "unknown",
            details={
                "gate_id": gate_result.gate_id,
                "violations": gate_result.total_violations,
                "failed_checks": gate_result.failed_checks,
                "status": gate_result.overall_status.value,
            },
            records_affected=gate_result.total_violations,
            severity="CRITICAL",
        )

        # Trigger recovery
        recovery_result = self.recovery_engine.recover(detection)

        self.recovery_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gate_result": gate_result,
            "recovery_result": recovery_result,
        })

