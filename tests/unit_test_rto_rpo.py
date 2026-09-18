
"""
tests/unit/test_rto_rpo.py
──────────────────────────
Tests for the RTO/RPO verification engine.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.verifier.rto_rpo import RTORPOVerifier, RTORPOReport
from src.config import RTOTarget, RPOTarget


class TestRTORPOReport:
    """Test RTO/RPO report data model."""

    def test_passed_report(self, rto_rpo_passed):
        r = rto_rpo_passed
        assert r.rto_met is True
        assert r.rpo_met is True
        assert r.verification_passed is True
        assert r.duplicates_introduced is False

    def test_failed_report(self, rto_rpo_failed):
        r = rto_rpo_failed
        assert r.rto_met is False
        assert r.rpo_met is False
        assert r.verification_passed is False

    def test_rto_calculation(self, rto_rpo_passed):
        r = rto_rpo_passed
        assert r.total_rto_seconds == r.detection_time_seconds + r.recovery_time_seconds

    def test_rto_within_target(self, rto_rpo_passed):
        assert rto_rpo_passed.total_rto_seconds < rto_rpo_passed.rto_target_seconds

    def test_rto_exceeds_target(self, rto_rpo_failed):
        assert rto_rpo_failed.total_rto_seconds > rto_rpo_failed.rto_target_seconds

    def test_zero_data_loss(self, rto_rpo_passed):
        assert rto_rpo_passed.records_lost == 0

    def test_data_loss_recorded(self, rto_rpo_failed):
        assert rto_rpo_failed.records_lost == 12


class TestRTORPOVerifier:
    """Test the RTO/RPO verification engine."""

    def test_verifier_passes_good_recovery(self, config, recovery_success):
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report.rto_met is True
        assert report.rpo_met is True
        assert report.verification_passed is True

    def test_verifier_fails_slow_recovery(self, config, recovery_success):
        """Recovery that exceeds RTO target should fail."""
        # Set very tight RTO target
        config.rto.target_seconds = 1  # 1 second — impossible to meet
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report.rto_met is False

    def test_verifier_fails_data_loss(self, config, recovery_partial):
        """Recovery with data loss should fail RPO check."""
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_partial)

        assert report.rpo_met is False
        assert report.records_lost > 0

    def test_verifier_detects_inconsistency(self, config, recovery_failed):
        """Failed recovery should be flagged as inconsistent."""
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_failed)

        assert report.data_consistent is False
        assert report.verification_passed is False

    def test_verifier_report_has_incident_id(self, config, recovery_success):
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report.incident_id is not None
        assert report.incident_id != ""

    def test_verifier_report_has_timestamps(self, config, recovery_success):
        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report.failure_detected_at is not None
        assert report.recovery_started_at is not None
        assert report.recovery_completed_at is not None

