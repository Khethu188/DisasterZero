
"""
tests/integration/test_orchestrator.py
──────────────────────────────────────
Integration tests for the DisasterZero orchestrator engine.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from src.config import FailureType


class TestOrchestratorEngine:
    """Test the orchestrator that coordinates all components."""

    def test_orchestrator_initialization(self, config):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)

        assert engine.config == config
        assert engine.simulator is not None
        assert engine.detector is not None
        assert engine.recovery_engine is not None
        assert engine.verifier is not None
        assert engine.report_generator is not None

    def test_orchestrator_registers_scenarios(self, config):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        scenarios = engine.get_available_scenarios()

        assert len(scenarios) > 0
        scenario_types = [s.failure_type for s in scenarios]
        assert FailureType.DATABRICKS_JOB_FAILURE in scenario_types

    @patch("src.orchestrator.engine.DisasterZeroEngine._execute_scenario")
    def test_run_single_scenario(self, mock_execute, config):
        """Orchestrator should execute a single scenario end-to-end."""
        from src.orchestrator.engine import DisasterZeroEngine

        mock_execute.return_value = MagicMock(overall_passed=True)

        engine = DisasterZeroEngine(config)
        result = engine.run_scenario(FailureType.DATABRICKS_JOB_FAILURE)

        mock_execute.assert_called_once()
        assert result is not None

    @patch("src.orchestrator.engine.DisasterZeroEngine._execute_scenario")
    def test_run_full_suite(self, mock_execute, config):
        """Orchestrator should run all scenarios in a suite."""
        from src.orchestrator.engine import DisasterZeroEngine

        mock_execute.return_value = MagicMock(overall_passed=True)

        engine = DisasterZeroEngine(config)
        suite = engine.run_full_suite()

        assert mock_execute.call_count >= 3  # At least 3 scenario types
        assert suite is not None

    @patch("src.orchestrator.engine.DisasterZeroEngine._execute_scenario")
    def test_suite_continues_after_failure(self, mock_execute, config):
        """Suite should continue running even if one scenario fails."""
        from src.orchestrator.engine import DisasterZeroEngine

        # First scenario fails, rest succeed
        mock_execute.side_effect = [
            MagicMock(overall_passed=False),
            MagicMock(overall_passed=True),
            MagicMock(overall_passed=True),
            MagicMock(overall_passed=True),
            MagicMock(overall_passed=True),
        ]

        engine = DisasterZeroEngine(config)
        suite = engine.run_full_suite()

        # All scenarios should have been attempted
        assert mock_execute.call_count >= 3

    def test_orchestrator_safety_mode(self, config):
        """Safety mode should ensure cleanup runs even on errors."""
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        assert engine.safety_mode is True  # Default on

    @patch("src.orchestrator.engine.DisasterZeroEngine._execute_scenario")
    def test_orchestrator_generates_suite_report(self, mock_execute, config, tmp_reports_dir):
        """Orchestrator should produce a suite report after all scenarios."""
        from src.orchestrator.engine import DisasterZeroEngine

        mock_execute.return_value = MagicMock(
            overall_passed=True,
            rto_seconds=47.3,
            records_lost=0,
            failure_type="databricks_job_failure",
        )

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir
        suite = engine.run_full_suite()

        assert suite.total_scenarios > 0
        assert suite.pass_rate >= 0

