
"""
src/detector/base.py
────────────────────
Base data models for failure detection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DetectionResult:
    """Result of a failure detection scan."""

    detected: bool = False
    failure_type: str = "none"
    target: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: Optional[datetime] = None
    affected_downstream: List[str] = field(default_factory=list)
    records_affected: int = 0
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL

    def __post_init__(self):
        if self.detected and self.detected_at is None:
            self.detected_at = datetime.now(timezone.utc)

