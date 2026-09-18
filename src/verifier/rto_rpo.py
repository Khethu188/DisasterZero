
"""
src/verifier/rto_rpo.py
───────────────────────
Measures and verifies Recovery Time Objective (RTO) and
Recovery Point Objective (RPO) against configured targets.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.config import RTOTarget, RPOTarget
from src.recovery.base import RecoveryResult


@dataclass
class RTORPOReport:
    """Complete RTO/RPO measurement report."""

    # Identity
    incident_id: str = ""
    failure_type: str = ""
    target: str = ""

    # Timestamps
    failure_detected_at: Optional[datetime] = None
    recovery_started_at: Optional[datetime] = None
    recovery_completed_at: Optional[datetime] = None

    # RTO Measurements
    detection_time_seconds: float = 0.0
    recovery_time_seconds: float = 0.0
    total_rto_seconds: float = 0.0
    rto_target_seconds: float = 0.0
    rto_met: bool = False

    # RPO Measurements
    records_after_recovery: int = 0
    records_lost: int = 0
    rpo_target_records: int = 0
    rpo_target_seconds: float = 0.0
    rpo_met: bool = False

    # Data Integrity
    fully_recovered: bool = False
    data_consistent: bool = False
    duplicates_introduced: bool = False

    # Overall
    verification_passed: bool = False

    def __post_init__(self):
        if not self.incident_id:
            self.incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"


class RTORPOVerifier:
    """Measure and verify RTO/RPO against targets."""

    def __init__(self, rto_target: RTOTarget, rpo_target: RPOTarget):
        self.rto_target = rto_target
        self.rpo_target = rpo_target

    def measure(self, recovery: RecoveryResult) -> RTORPOReport:
        """Measure RTO/RPO from a recovery result."""
        detection = recovery.detection

        # Calculate timing
        detection_time = 0.0
        if detection and detection.detected_at and recovery.recovery_start:
            detection_time = (recovery.recovery_start - detection.detected_at).total_seconds()

        recovery_time = recovery.total_duration_seconds
        total_rto = detection_time + recovery_time

        # RTO check
        rto_met = total_rto <= self.rto_target.target_seconds

        # RPO check
        rpo_met = (
            recovery.records_lost <= self.rpo_target.target_records
            and recovery.data_consistent
        )

        # Overall verification
        verification_passed = rto_met and rpo_met and recovery.recovered

        return RTORPOReport(
            failure_type=detection.failure_type if detection else "unknown",
            target=detection.target if detection else "",
            failure_detected_at=detection.detected_at if detection else None,
            recovery_started_at=recovery.recovery_start,
            recovery_completed_at=recovery.recovery_end,
            detection_time_seconds=detection_time,
            recovery_time_seconds=recovery_time,
            total_rto_seconds=total_rto,
            rto_target_seconds=self.rto_target.target_seconds,
            rto_met=rto_met,
            records_after_recovery=recovery.records_recovered,
            records_lost=recovery.records_lost,
            rpo_target_records=self.rpo_target.target_records,
            rpo_target_seconds=self.rpo_target.target_seconds,
            rpo_met=rpo_met,
            fully_recovered=recovery.recovered,
            data_consistent=recovery.data_consistent,
            duplicates_introduced=False,
            verification_passed=verification_passed,
        )

