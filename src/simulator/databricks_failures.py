
"""
src/simulator/databricks_failures.py
─────────────────────────────────────
Simulates Databricks failures: job cancellation, data corruption,
cluster termination.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from src.config import DisasterZeroConfig, FailureType


@dataclass
class InjectionResult:
    """Result of a failure injection."""
    injection_id: str = ""
    failure_type: FailureType = FailureType.DATABRICKS_JOB_FAILURE
    target: str = ""
    injected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None
    cleanup_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.injection_id:
            self.injection_id = f"INJ-{uuid.uuid4().hex[:8].upper()}"


class DatabricksFailureSimulator:
    """Inject failures into Databricks environment."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.host = config.databricks.host.rstrip("/")
        self.headers = {"Authorization": f"Bearer {config.databricks.token}"}

    def inject_failure(
        self,
        failure_type: FailureType,
        table_name: Optional[str] = None,
        **kwargs,
    ) -> InjectionResult:
        """Inject a specific failure type."""
        handlers = {
            FailureType.DATABRICKS_JOB_FAILURE: self._inject_job_failure,
            FailureType.DATABRICKS_CLUSTER_TERMINATION: self._inject_cluster_termination,
            FailureType.PIPELINE_CORRUPTION: self._inject_data_corruption,
        }

        handler = handlers.get(failure_type)
        if handler is None:
            raise ValueError(f"Unsupported failure type for Databricks: {failure_type}")

        return handler(table_name=table_name, **kwargs)

    def cleanup(self, injection: InjectionResult) -> None:
        """Reverse the injected failure (safety net)."""
        cleanup_handlers = {
            FailureType.DATABRICKS_JOB_FAILURE: self._cleanup_job_failure,
            FailureType.DATABRICKS_CLUSTER_TERMINATION: self._cleanup_cluster,
            FailureType.PIPELINE_CORRUPTION: self._cleanup_corruption,
        }

        handler = cleanup_handlers.get(injection.failure_type)
        if handler:
            handler(injection)

    # ── Injection Methods ──

    def _inject_job_failure(self, **kwargs) -> InjectionResult:
        """Cancel a running job to simulate failure."""
        job_id = self.config.databricks.job_id

        # Trigger a new run
        resp = requests.post(
            f"{self.host}/api/2.1/jobs/run-now",
            headers=self.headers,
            json={"job_id": int(job_id)},
            timeout=30,
        )
        resp.raise_for_status()
        run_id = str(resp.json().get("run_id", "unknown"))

        # Cancel it immediately to simulate failure
        requests.post(
            f"{self.host}/api/2.1/jobs/runs/cancel",
            headers=self.headers,
            json={"run_id": run_id},
            timeout=30,
        )

        return InjectionResult(
            failure_type=FailureType.DATABRICKS_JOB_FAILURE,
            target=f"job:{job_id}/run:{run_id}",
            run_id=run_id,
            details={"job_id": job_id, "run_id": run_id, "action": "cancel"},
            cleanup_info={"run_id": run_id},
        )

    def _inject_cluster_termination(self, **kwargs) -> InjectionResult:
        """Terminate a cluster to simulate failure."""
        cluster_id = self.config.databricks.cluster_id

        requests.post(
            f"{self.host}/api/2.0/clusters/delete",
            headers=self.headers,
            json={"cluster_id": cluster_id},
            timeout=30,
        )

        return InjectionResult(
            failure_type=FailureType.DATABRICKS_CLUSTER_TERMINATION,
            target=f"cluster:{cluster_id}",
            details={"cluster_id": cluster_id, "action": "terminate"},
            cleanup_info={"cluster_id": cluster_id},
        )

    def _inject_data_corruption(self, table_name: Optional[str] = None, **kwargs) -> InjectionResult:
        """Inject corrupt records into a Delta table."""
        table = table_name or self.config.databricks.silver_table

        corrupt_sql = f"""
        INSERT INTO {table} (transaction_id, amount, currency, status, processed_at)
        VALUES
            ('CORRUPT-001', -999.99, NULL, 'INVALID', current_timestamp()),
            ('CORRUPT-002', NULL, 'XXX', 'INVALID', current_timestamp()),
            ('CORRUPT-003', 0.01, NULL, NULL, current_timestamp())
        """

        resp = requests.post(
            f"{self.host}/api/2.0/sql/statements",
            headers=self.headers,
            json={
                "warehouse_id": self.config.databricks.warehouse_id,
                "statement": corrupt_sql,
                "wait_timeout": "30s",
            },
            timeout=60,
        )

        return InjectionResult(
            failure_type=FailureType.PIPELINE_CORRUPTION,
            target=table,
            details={
                "table": table,
                "corrupt_ids": ["CORRUPT-001", "CORRUPT-002", "CORRUPT-003"],
                "action": "insert_corrupt_records",
            },
            cleanup_info={
                "table": table,
                "corrupt_ids": ["CORRUPT-001", "CORRUPT-002", "CORRUPT-003"],
            },
        )

    # ── Cleanup Methods ──

    def _cleanup_job_failure(self, injection: InjectionResult) -> None:
        """No cleanup needed — cancelled run is already terminal."""
        pass

    def _cleanup_cluster(self, injection: InjectionResult) -> None:
        """Restart the terminated cluster."""
        cluster_id = injection.cleanup_info.get("cluster_id")
        if cluster_id:
            requests.post(
                f"{self.host}/api/2.0/clusters/start",
                headers=self.headers,
                json={"cluster_id": cluster_id},
                timeout=30,
            )

    def _cleanup_corruption(self, injection: InjectionResult) -> None:
        """Remove injected corrupt records."""
        table = injection.cleanup_info.get("table", "")
        corrupt_ids = injection.cleanup_info.get("corrupt_ids", [])
        if table and corrupt_ids:
            ids_str = ", ".join(f"'{cid}'" for cid in corrupt_ids)
            cleanup_sql = f"DELETE FROM {table} WHERE transaction_id IN ({ids_str})"

            requests.post(
                f"{self.host}/api/2.0/sql/statements",
                headers=self.headers,
                json={
                    "warehouse_id": self.config.databricks.warehouse_id,
                    "statement": cleanup_sql,
                    "wait_timeout": "30s",
                },
                timeout=60,
            )

