
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
    QualityGateResult,
    QualityStatus,
)
from src.recovery.databricks_recovery import DatabricksRecoveryEngine


class TestDataTrustBridgeIntegration:
    """Test the full DataTrust → DisasterZero integration flow."""

    def test_bridge_initialization(self, config):
        bridge = DataTrustBridge(config)
        assert bridge.quality_gate is not None
        assert bridge.recovery_engine is None

    def test_connect_to_disasterzero(self, config):
        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)
        bridge.connect_to_disasterzero(recovery)

        assert bridge.recovery_engine == recovery
        assert bridge.quality_gate.recovery_callback is not None

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_quality_gate_pass_no_recovery(self, mock_evaluate, config):
        """When quality gate passes, no recovery should be triggered."""
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
        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.CRITICAL,
            total_checks=12,
            passed_checks=9,
            failed_checks=3,
            total_violations=47,
            records_quarantined=47,
            triggered_recovery=True,
        )

        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)
        bridge.connect_to_disasterzero(recovery)

        bridge._on_quality_failure(mock_evaluate.return_value)

        recovery.recover.assert_called_once()

    def test_recovery_history_tracked(self, config):
        """Bridge should track all recovery events."""
        bridge = DataTrustBridge(config)
        assert len(bridge.recovery_history) == 0

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_post_transformation_gate_checks_all_layers(self, mock_evaluate, config):
        """Post-transformation gate should check Silver then Gold."""
        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.PASSED,
            total_checks=12,
            passed_checks=12,
            failed_checks=0,
        )

        bridge = DataTrustBridge(config)
        bridge.run_post_transformation_gate(
            silver_table="transactions.silver.processed",
            gold_table="transactions.gold.daily_summary",
        )

        # Should be called twice — once for Silver, once for Gold
        assert mock_evaluate.call_count == 2
        calls = mock_evaluate.call_args_list
        assert "silver" in calls[0][0][0]
        assert "gold" in calls[1][0][0]

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_warning_status_does_not_trigger_recovery(self, mock_evaluate, config):
        """WARNING status should log but NOT trigger recovery."""
        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.WARNING,
            total_checks=12,
            passed_checks=11,
            failed_checks=1,
            total_violations=3,
        )

        bridge = DataTrustBridge(config)
        recovery = MagicMock(spec=DatabricksRecoveryEngine)
        bridge.connect_to_disasterzero(recovery)

        result = bridge.run_quality_gate("transactions.silver.processed")

        assert result.overall_status == QualityStatus.WARNING
        recovery.recover.assert_not_called()

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_multiple_gate_runs_accumulate_history(self, mock_evaluate, config):
        """Multiple quality gate runs should build up history."""
        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.PASSED,
            total_checks=12,
            passed_checks=12,
            failed_checks=0,
        )

        bridge = DataTrustBridge(config)

        for _ in range(5):
            bridge.run_quality_gate("transactions.silver.processed")

        assert len(bridge.gate_history) == 5

    @patch.object(DataTrustQualityGate, "evaluate")
    def test_gate_result_includes_table_name(self, mock_evaluate, config):
        """Result should reference the table that was checked."""
        mock_evaluate.return_value = QualityGateResult(
            table="transactions.silver.processed",
            overall_status=QualityStatus.PASSED,
            total_checks=12,
            passed_checks=12,
            failed_checks=0,
        )

        bridge = DataTrustBridge(config)
        result = bridge.run_quality_gate("transactions.silver.processed")

        assert result.table == "transactions.silver.processed"

