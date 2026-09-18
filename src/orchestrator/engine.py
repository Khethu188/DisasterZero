"""
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
