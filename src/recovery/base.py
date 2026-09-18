
"""
src/recovery/base.py
────────────────────
Base data models for recovery operations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.detector.base import DetectionResult


@dataclass
class RecoveryAction:
    """A single recovery step."""
    action: str = ""
    target: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: bool = False
    duration_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Complete result of a recovery operation."""
    detection: Optional[DetectionResult] = None
    actions: List[RecoveryAction] = field(default_factory=list)
    recovered: bool = False
    recovery_start: Optional[datetime] = None
    recovery_end: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    records_recovered: int = 0
    records_lost: int = 0
    data_consistent: bool = False

