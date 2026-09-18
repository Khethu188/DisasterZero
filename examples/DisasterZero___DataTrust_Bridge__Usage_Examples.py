
"""
examples/datatrust_bridge_demo.py
─────────────────────────────────
Demonstrates the full DataTrust ↔ DisasterZero integration.

Run this after the pipeline has completed at least one run.
"""

from src.config import DisasterZeroConfig, FailureType
from src.datatrust_bridge import DataTrustBridge
from src.recovery.databricks_recovery import DatabricksRecoveryEngine
from src.verifier.rto_rpo import RTORPOVerifier
from src.simulator.databricks_failures import DatabricksFailureSimulator


def demo_quality_gate_only():
    """
    Demo 1: Run DataTrust quality checks without recovery.
    Use this to see what the quality gate catches.
    """
    print("=" * 60)
    print("DEMO 1: Quality Gate Only (no recovery)")
    print("=" * 60)

    config = DisasterZeroConfig()
    bridge = DataTrustBridge(config)

    # Run quality gate on Silver layer
    result = bridge.run_quality_gate(
        table="transactions.silver.processed",
        layer="silver",
    )

    print(f"\nResult: {result.overall_status.value}")
    print(f"Checks: {result.passed_checks}/{result.total_checks} passed")
    print(f"Violations: {result.total_violations}")

    return result


def demo_full_integration():
    """
    Demo 2: Full DataTrust + DisasterZero integration.
    Injects corruption, then lets the system detect and recover.
    """
    print("=" * 60)
    print("DEMO 2: Full DataTrust ↔ DisasterZero Integration")
    print("=" * 60)

    config = DisasterZeroConfig()

    # Set up all components
    bridge = DataTrustBridge(config)
    recovery_engine = DatabricksRecoveryEngine(config)
    rto_rpo = RTORPOVerifier(config.rto, config.rpo)

    # Connect DataTrust to DisasterZero
    bridge.connect_to_disasterzero(recovery_engine, rto_rpo)

    # Step 1: Verify pipeline is healthy before injection
    print("\n── Pre-injection quality check ──")
    pre_result = bridge.run_quality_gate(
        table="transactions.silver.processed",
        layer="silver",
    )
    assert pre_result.overall_status.value in ("PASSED", "WARNING"), \
        "Pipeline should be healthy before we inject failures!"

    # Step 2: Inject data corruption (simulating a real failure)
    print("\n── Injecting data corruption ──")
    simulator = DatabricksFailureSimulator(config)
    failure = simulator.inject_failure(
        FailureType.PIPELINE_CORRUPTION,
        table_name="transactions.silver.processed",
    )
    print(f"Injected: {failure.description}")

    # Step 3: Run quality gate — this should detect the corruption
    #         and automatically trigger recovery
    print("\n── Running quality gate (should detect corruption) ──")
    post_result = bridge.run_quality_gate(
        table="transactions.silver.processed",
        layer="silver",
    )

    # Step 4: Check recovery history
    print("\n── Recovery History ──")
    for i, entry in enumerate(bridge.recovery_history):
        report = entry.get("rto_rpo_report")
        if report:
            print(f"  Recovery {i+1}:")
            print(f"    RTO: {report.total_rto_seconds:.1f}s "
                  f"({'MET' if report.rto_met else 'MISSED'})")
            print(f"    RPO: {report.records_lost} records lost "
                  f"({'MET' if report.rpo_met else 'MISSED'})")
            print(f"    Verified: {report.verification_passed}")

    return bridge.recovery_history


def demo_post_pipeline_gate():
    """
    Demo 3: Run quality gates on all layers after a pipeline run.
    This is what you'd call at the end of the Lakeflow workflow.
    """
    print("=" * 60)
    print("DEMO 3: Post-Pipeline Quality Gate (all layers)")
    print("=" * 60)

    config = DisasterZeroConfig()
    bridge = DataTrustBridge(config)
    recovery_engine = DatabricksRecoveryEngine(config)
    bridge.connect_to_disasterzero(recovery_engine)

    summary = bridge.run_post_transformation_gate(
        pipeline_run_id="manual-demo-001"
    )

    print(f"\nAll passed: {summary['all_passed']}")
    for layer, info in summary["results"].items():
        print(f"  {layer}: {info['status']}")

    return summary


if __name__ == "__main__":
    import sys

    demos = {
        "1": demo_quality_gate_only,
        "2": demo_full_integration,
        "3": demo_post_pipeline_gate,
    }

    if len(sys.argv) > 1 and sys.argv[1] in demos:
        demos[sys.argv[1]]()
    else:
        print("Usage: python datatrust_bridge_demo.py [1|2|3]")
        print("  1 — Quality gate only")
        print("  2 — Full DataTrust + DisasterZero integration")
        print("  3 — Post-pipeline quality gate (all layers)")

