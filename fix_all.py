
"""
fix_all.py — Run this once to fix all 24 test failures.
Usage: python fix_all.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))


def write_file(rel_path, content):
    path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  WROTE: {rel_path}")


# ─────────────────────────────────────────────────────────────
# FIX 1: src/orchestrator/engine.py (fixes 7 orchestrator tests)
# ─────────────────────────────────────────────────────────────
write_file("src/orchestrator/engine.py", '''"""
src/orchestrator/engine.py
Orchestrates disaster recovery scenarios end-to-end.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import DisasterZeroConfig, FailureType
from src.simulator.databricks_failures import DatabricksFailureSimulator
from src.simulator.aws_failures import AWSFailureSimulator
from src.detector.databricks_detector import DatabricksFailureDetector
from src.detector.aws_detector import AWSFailureDetector
from src.recovery.databricks_recovery import DatabricksRecoveryEngine
from src.recovery.aws_recovery import AWSRecoveryEngine
from src.verifier.rto_rpo import RTORPOVerifier
from src.reporting.report_generator import RecoveryReportGenerator


@dataclass
class Scenario:
    name: str = ""
    failure_type: FailureType = FailureType.DATABRICKS_JOB_FAILURE
    description: str = ""


@dataclass
class ScenarioResult:
    scenario_name: str = ""
    failure_type: str = ""
    overall_passed: bool = False
    rto_seconds: float = 0.0
    records_lost: int = 0
    incident_id: str = ""
    error: Optional[str] = None


@dataclass
class SuiteReport:
    suite_id: str = ""
    total_scenarios: int = 0
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    pass_rate: float = 0.0
    results: List[ScenarioResult] = field(default_factory=list)

    def __post_init__(self):
        if not self.suite_id:
            self.suite_id = "SUITE-" + uuid.uuid4().hex[:8].upper()


class DisasterZeroEngine:
    """Orchestrate disaster recovery test scenarios."""

    def __init__(self, config: DisasterZeroConfig, safety_mode: bool = True):
        self.config = config
        self.safety_mode = safety_mode

        # Initialize all components
        self.simulator = DatabricksFailureSimulator(config)
        self.aws_simulator = AWSFailureSimulator(config)
        self.detector = DatabricksFailureDetector(config)
        self.aws_detector = AWSFailureDetector(config)
        self.recovery_engine = DatabricksRecoveryEngine(config)
        self.aws_recovery = AWSRecoveryEngine(config)
        self.verifier = RTORPOVerifier(config.rto, config.rpo)
        self.report_generator = RecoveryReportGenerator(config)

        self._scenarios = [
            Scenario("Databricks Job Failure", FailureType.DATABRICKS_JOB_FAILURE, "Cancel a running job"),
            Scenario("Databricks Cluster Termination", FailureType.DATABRICKS_CLUSTER_TERMINATION, "Terminate cluster"),
            Scenario("Pipeline Data Corruption", FailureType.PIPELINE_CORRUPTION, "Inject corrupt records"),
            Scenario("EC2 Instance Stop", FailureType.EC2_INSTANCE_STOP, "Stop EC2 instance"),
            Scenario("S3 Access Denied", FailureType.S3_ACCESS_DENIED, "Block S3 access"),
        ]

    def get_available_scenarios(self) -> List[Scenario]:
        return list(self._scenarios)

    def run_scenario(self, failure_type: FailureType) -> ScenarioResult:
        scenario = None
        for s in self._scenarios:
            if s.failure_type == failure_type:
                scenario = s
                break
        if scenario is None:
            return ScenarioResult(overall_passed=False, error="Scenario not found")
        return self._execute_scenario(scenario)

    def run_full_suite(self) -> SuiteReport:
        results = []
        for scenario in self._scenarios:
            result = self._execute_scenario(scenario)
            results.append(result)

        passed = sum(1 for r in results if r.overall_passed)
        failed = len(results) - passed

        return SuiteReport(
            total_scenarios=len(results),
            scenarios_passed=passed,
            scenarios_failed=failed,
            pass_rate=(passed / len(results) * 100) if results else 0.0,
            results=results,
        )

    def _execute_scenario(self, scenario: Scenario) -> ScenarioResult:
        try:
            # Simulate
            if scenario.failure_type in (
                FailureType.DATABRICKS_JOB_FAILURE,
                FailureType.DATABRICKS_CLUSTER_TERMINATION,
                FailureType.PIPELINE_CORRUPTION,
            ):
                injection = self.simulator.inject_failure(scenario.failure_type)
                detection = self.detector.detect(run_id=getattr(injection, "run_id", None) or "unknown")
                recovery = self.recovery_engine.recover(detection)
            else:
                injection = self.aws_simulator.inject_failure(scenario.failure_type)
                detection = self.aws_detector.detect_ec2(instance_id=self.config.aws.ec2_instance_id)
                recovery = self.aws_recovery.recover(detection)

            rto_rpo = self.verifier.measure(recovery)

            report = self.report_generator.build_incident_report(
                scenario_name=scenario.name,
                detection=detection,
                recovery=recovery,
                rto_rpo=rto_rpo,
            )

            if self.safety_mode:
                try:
                    self.simulator.cleanup(injection)
                except Exception:
                    pass

            return ScenarioResult(
                scenario_name=scenario.name,
                failure_type=scenario.failure_type.value,
                overall_passed=rto_rpo.verification_passed,
                rto_seconds=rto_rpo.total_rto_seconds,
                records_lost=rto_rpo.records_lost,
                incident_id=report.incident_id,
            )

        except Exception as e:
            return ScenarioResult(
                scenario_name=scenario.name,
                failure_type=scenario.failure_type.value,
                overall_passed=False,
                error=str(e),
            )


# Alias for backward compatibility
DisasterZeroOrchestrator = DisasterZeroEngine
''')


# ─────────────────────────────────────────────────────────────
# FIX 2: src/reporting/report_generator.py (fixes 2 pipeline tests)
# ─────────────────────────────────────────────────────────────
write_file("src/reporting/report_generator.py", '''"""
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
''')


# ─────────────────────────────────────────────────────────────
# FIX 3: src/simulator/databricks_failures.py — fix int(run_id)
# ─────────────────────────────────────────────────────────────
path3 = os.path.join(BASE, "src", "simulator", "databricks_failures.py")
content3 = open(path3, "r", encoding="utf-8").read()
content3 = content3.replace('json={"run_id": int(run_id)}', 'json={"run_id": run_id}')
with open(path3, "w", encoding="utf-8") as f:
    f.write(content3)
print("  FIXED: src/simulator/databricks_failures.py (int(run_id) -> run_id)")


# ─────────────────────────────────────────────────────────────
# FIX 4: src/datatrust_bridge/quality_gate.py — add recovery_callback property
# ─────────────────────────────────────────────────────────────
path4 = os.path.join(BASE, "src", "datatrust_bridge", "quality_gate.py")
content4 = open(path4, "r", encoding="utf-8").read()
if "@property" not in content4 and "recovery_callback" in content4:
    # Add property after _recovery_callback = None
    content4 = content4.replace(
        "        self._recovery_callback = None",
        """        self._recovery_callback = None

    @property
    def recovery_callback(self):
        return self._recovery_callback

    @recovery_callback.setter
    def recovery_callback(self, value):
        self._recovery_callback = value"""
    )
    with open(path4, "w", encoding="utf-8") as f:
        f.write(content4)
    print("  FIXED: src/datatrust_bridge/quality_gate.py (added recovery_callback property)")
else:
    print("  SKIP: quality_gate.py already has property or different structure")


# ─────────────────────────────────────────────────────────────
# FIX 5: tests/test_quality_gate.py — add QualityRulesRegistry to imports
# ─────────────────────────────────────────────────────────────
path5 = os.path.join(BASE, "tests", "test_quality_gate.py")
content5 = open(path5, "r", encoding="utf-8").read()
if "QualityRulesRegistry" not in content5.split("import")[1] if "import" in content5 else True:
    # Find the import block and add QualityRulesRegistry
    content5 = content5.replace(
        "from src.datatrust_bridge.quality_gate import (",
        "from src.datatrust_bridge.quality_gate import (\n    QualityRulesRegistry,"
    )
    # Make sure we don't double-add
    content5 = content5.replace(
        "    QualityRulesRegistry,\n    QualityRulesRegistry,",
        "    QualityRulesRegistry,"
    )
    with open(path5, "w", encoding="utf-8") as f:
        f.write(content5)
    print("  FIXED: tests/test_quality_gate.py (added QualityRulesRegistry import)")
else:
    print("  SKIP: test_quality_gate.py already imports QualityRulesRegistry")


# ─────────────────────────────────────────────────────────────
# CLEANUP: Remove all __pycache__ directories
# ─────────────────────────────────────────────────────────────
import shutil
count = 0
for root, dirs, files in os.walk(BASE):
    for d in dirs:
        if d == "__pycache__":
            shutil.rmtree(os.path.join(root, d))
            count += 1
print(f"  CLEANED: Removed {count} __pycache__ directories")


print("\n" + "=" * 50)
print("ALL FIXES APPLIED! Now run:")
print("  python -m pytest tests/ -v")
print("=" * 50)

