
"""
tests/unit/test_quality_gate.py
───────────────────────────────
Tests for the DataTrust Quality Gate (bridge).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.datatrust_bridge.quality_gate import (
    QualityRulesRegistry,
    DataTrustQualityGate,
    QualityGateResult,
    QualityCheckResult,
    QualityRule,
    QualityStatus,
    CheckType,
)


class TestQualityStatus:
    """Test quality status enum."""

    def test_all_statuses_exist(self):
        assert QualityStatus.PASSED.value == "PASSED"
        assert QualityStatus.WARNING.value == "WARNING"
        assert QualityStatus.FAILED.value == "FAILED"
        assert QualityStatus.CRITICAL.value == "CRITICAL"

    def test_status_ordering(self):
        """CRITICAL > FAILED > WARNING > PASSED in severity."""
        statuses = [QualityStatus.PASSED, QualityStatus.WARNING,
                    QualityStatus.FAILED, QualityStatus.CRITICAL]
        # Just verify they're all distinct
        assert len(set(statuses)) == 4


class TestCheckType:
    """Test check type enum."""

    def test_all_check_types(self):
        expected = ["completeness", "uniqueness", "validity",
                    "consistency", "freshness", "accuracy",
                    "record_count", "schema"]
        actual = [ct.value for ct in CheckType]
        for ct in expected:
            assert ct in actual


class TestQualityRule:
    """Test quality rule data model."""

    def test_rule_creation(self):
        rule = QualityRule(
            rule_id="TEST-001",
            name="Test Rule",
            check_type=CheckType.COMPLETENESS,
            table="test_table",
            column="test_column",
            sql_check="SELECT COUNT(*) FROM test_table WHERE test_column IS NULL",
            threshold=0.0,
            severity="HIGH",
        )
        assert rule.rule_id == "TEST-001"
        assert rule.enabled is True

    def test_rule_disabled(self):
        rule = QualityRule(enabled=False)
        assert rule.enabled is False


class TestQualityRulesRegistry:
    """Test the quality rules registry."""

    def test_silver_rules_count(self):
        rules = QualityRulesRegistry.get_silver_rules()
        assert len(rules) >= 10  # At least 10 Silver rules

    def test_gold_rules_count(self):
        rules = QualityRulesRegistry.get_gold_rules()
        assert len(rules) >= 3  # At least 3 Gold rules

    def test_silver_rules_have_ids(self):
        rules = QualityRulesRegistry.get_silver_rules()
        for rule in rules:
            assert rule.rule_id.startswith("SLV-")

    def test_gold_rules_have_ids(self):
        rules = QualityRulesRegistry.get_gold_rules()
        for rule in rules:
            assert rule.rule_id.startswith("GLD-")

    def test_all_rules_have_sql(self):
        all_rules = (
            QualityRulesRegistry.get_silver_rules()
            + QualityRulesRegistry.get_gold_rules()
        )
        for rule in all_rules:
            assert rule.sql_check.strip() != "", f"Rule {rule.rule_id} has no SQL"

    def test_critical_rules_exist(self):
        """Certain rules must be CRITICAL severity."""
        rules = QualityRulesRegistry.get_silver_rules()
        critical_ids = [r.rule_id for r in rules if r.severity == "CRITICAL"]
        assert "SLV-001" in critical_ids  # NULL transaction IDs
        assert "SLV-002" in critical_ids  # NULL amounts
        assert "SLV-010" in critical_ids  # Duplicate IDs

    def test_custom_table_name(self):
        """Rules should use the provided table name."""
        custom_table = "my_catalog.my_schema.my_table"
        rules = QualityRulesRegistry.get_silver_rules(table=custom_table)
        for rule in rules:
            assert custom_table in rule.sql_check

    def test_check_types_covered(self):
        """Silver rules should cover multiple check types."""
        rules = QualityRulesRegistry.get_silver_rules()
        types_covered = {r.check_type for r in rules}
        assert CheckType.COMPLETENESS in types_covered
        assert CheckType.UNIQUENESS in types_covered
        assert CheckType.VALIDITY in types_covered
        assert CheckType.CONSISTENCY in types_covered
        assert CheckType.FRESHNESS in types_covered


class TestQualityGateResult:
    """Test quality gate result data model."""

    def test_passed_gate(self, quality_gate_passed):
        g = quality_gate_passed
        assert g.overall_status == QualityStatus.PASSED
        assert g.failed_checks == 0
        assert g.total_violations == 0

    def test_failed_gate(self, quality_gate_failed):
        g = quality_gate_failed
        assert g.overall_status == QualityStatus.CRITICAL
        assert g.failed_checks == 3
        assert g.total_violations == 47
        assert g.triggered_recovery is True

    def test_gate_has_id(self, quality_gate_passed):
        assert quality_gate_passed.gate_id.startswith("QG-")

    def test_gate_tracks_quarantine(self, quality_gate_failed):
        assert quality_gate_failed.records_quarantined == 47


class TestDataTrustQualityGate:
    """Test the quality gate engine."""

    def test_gate_initialization(self, config):
        gate = DataTrustQualityGate(config)
        assert gate.config == config
        assert gate.registry is not None

    def test_register_recovery_callback(self, config):
        gate = DataTrustQualityGate(config)
        callback = MagicMock()
        gate.register_recovery_callback(callback)
        assert gate.recovery_callback == callback

    @patch.object(DataTrustQualityGate, "_execute_sql_scalar", return_value=0)
    @patch.object(DataTrustQualityGate, "_get_record_count", return_value=10000)
    @patch.object(DataTrustQualityGate, "_write_audit_record")
    def test_evaluate_all_pass(self, mock_audit, mock_count, mock_sql, config):
        """All checks passing should return PASSED status."""
        gate = DataTrustQualityGate(config)
        result = gate.evaluate("transactions.silver.processed")

        assert result.overall_status == QualityStatus.PASSED
        assert result.failed_checks == 0

    @patch.object(DataTrustQualityGate, "_execute_sql_scalar", return_value=100)
    @patch.object(DataTrustQualityGate, "_get_record_count", return_value=10000)
    @patch.object(DataTrustQualityGate, "_quarantine_violations", return_value=100)
    @patch.object(DataTrustQualityGate, "_write_audit_record")
    def test_evaluate_with_violations(self, mock_audit, mock_quarantine, mock_count, mock_sql, config):
        """Violations should trigger FAILED/CRITICAL status."""
        gate = DataTrustQualityGate(config)
        result = gate.evaluate("transactions.silver.processed")

        assert result.overall_status in (QualityStatus.FAILED, QualityStatus.CRITICAL)
        assert result.total_violations > 0

    @patch.object(DataTrustQualityGate, "_execute_sql_scalar", return_value=100)
    @patch.object(DataTrustQualityGate, "_get_record_count", return_value=10000)
    @patch.object(DataTrustQualityGate, "_quarantine_violations", return_value=100)
    @patch.object(DataTrustQualityGate, "_write_audit_record")
    def test_critical_failure_triggers_callback(self, mock_audit, mock_quarantine, mock_count, mock_sql, config):
        """CRITICAL failures should trigger the recovery callback."""
        gate = DataTrustQualityGate(config)
        callback = MagicMock()
        gate.register_recovery_callback(callback)

        gate.evaluate("transactions.silver.processed")

        callback.assert_called_once()

