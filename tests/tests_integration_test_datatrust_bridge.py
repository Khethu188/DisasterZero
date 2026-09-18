
"""
tests/integration/test_datatrust_bridge.py
──────────────────────────────────────────
Integration tests for the DataTrust ↔ DisasterZero bridge.
Tests the full flow: quality gate → quarantine → recovery trigger.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from src.datatrust_bridge import DataTrustBridge
from src.datatrust_bridge.quality_gate import (
    DataTrustQualityGate,
    QualityStatus,
)
from src.recovery.databricks_recovery import DatabricksRecoveryEngine


class TestDataTrustBridgeIntegration:
    """Test the full DataTrust → DisasterZero integration flow."""

    def test_bridge_initialization(self, config):
        bridge = DataTrustBridge(config)
        assert bridge.quality_gate is not None
        assert bridge.recovery_engine is None  # Not connected yet

    def test_connect_to_disasterzero(self, config):
        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)

        bridge.connect_to_disasterzero(recovery)

        assert bridge.recovery_engine == recovery
        assert bridge.quality_gate.recovery_callback is not None

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_quality_gate_pass_no_recovery(self, mock_evaluate, config):
        """When quality gate passes, no recovery should be triggered."""
        from src.datatrust_bridge.quality_gate import QualityGateResult

        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.PASSED,
            total_checks=12,
            passed_checks=12,
            failed_checks=0,
        )

        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)
        bridge.connect_to_disasterzero(recovery)

        result = bridge.run_quality_gate("transactions.silver.processed")

        assert result.overall_status == QualityStatus.PASSED
        recovery.recover.assert_not_called()

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_critical_failure_triggers_recovery(self, mock_evaluate, config):
        """CRITICAL quality gate failure should trigger recovery."""
        from src.datatrust_bridge.quality_gate import QualityGateResult

        # First call: CRITICAL failure, second call: verification passes
        mock_evaluate.side_effect = [
            QualityGateResult(
                overall_status=QualityStatus.CRITICAL,
                total_checks=12,
                passed_checks=9,
                failed_checks=3,
                total_violations=47,
                records_quarantined=47,
                triggered_recovery=True,
            ),
            QualityGateResult(
                overall_status=QualityStatus.PASSED,
                total_checks=12,
                passed_checks=12,
            ),
        ]

        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)
        bridge.connect_to_disasterzero(recovery)

        # Manually trigger the callback to simulate the flow
        bridge._on_quality_failure(mock_evaluate.side_effect[0])

        recovery.recover.assert_called_once()

    def test_recovery_history_tracked(self, config):
        """Bridge should track all recovery events."""
        bridge = DataTrustBridge(config)
        assert len(bridge.recovery_history) == 0

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_post_transformation_gate_checks_all_layers(self, mock_evaluate, config):
        """Post-transformation gate should check Silver then Gold."""
        from src.datatrust_bridge.quality_gate import QualityGateResult

        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.
