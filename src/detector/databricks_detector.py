
"""
src/detector/databricks_detector.py
────────────────────────────────────
Detects failures in Databricks jobs, clusters, and pipelines.
"""

import requests
from datetime import datetime, timezone
from typing import Optional

from src.config import DisasterZeroConfig
from src.detector.base import DetectionResult


class DatabricksFailureDetector:
    """Detect Databricks job and cluster failures."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.host = config.databricks.host.rstrip("/")
        self.headers = {"Authorization": f"Bearer {config.databricks.token}"}

    def detect(self, run_id: Optional[str] = None, job_id: Optional[str] = None) -> DetectionResult:
        """
        Check a Databricks job run for failures.
        If no run_id provided, checks the latest run of the configured job.
        """
        try:
            if run_id is None:
                run_id = self._get_latest_run_id(job_id or self.config.databricks.job_id)
                if run_id is None:
                    return DetectionResult(detected=False, failure_type="none")

            return self._check_run(run_id)

        except Exception as e:
            return DetectionResult(
                detected=True,
                failure_type="databricks_api_error",
                target=f"job:{job_id or self.config.databricks.job_id}",
                details={"error": str(e), "error_type": type(e).__name__},
                severity="HIGH",
            )

    def detect_cluster(self, cluster_id: Optional[str] = None) -> DetectionResult:
        """Check if a Databricks cluster has been terminated unexpectedly."""
        cid = cluster_id or self.config.databricks.cluster_id
        try:
            resp = requests.get(
                f"{self.host}/api/2.0/clusters/get",
                headers=self.headers,
                params={"cluster_id": cid},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            state = data.get("state", "")
            if state == "TERMINATED":
                termination = data.get("termination_reason", {})
                return DetectionResult(
                    detected=True,
                    failure_type="databricks_cluster_termination",
                    target=f"cluster:{cid}",
                    details={
                        "cluster_id": cid,
                        "cluster_name": data.get("cluster_name", ""),
                        "state": state,
                        "termination_code": termination.get("code", "UNKNOWN"),
                        "termination_message": termination.get("message", ""),
                    },
                    severity="HIGH",
                )

            return DetectionResult(detected=False, failure_type="none")

        except Exception as e:
            return DetectionResult(
                detected=True,
                failure_type="databricks_api_error",
                target=f"cluster:{cid}",
                details={"error": str(e)},
                severity="HIGH",
            )

    def _check_run(self, run_id: str) -> DetectionResult:
        """Check a specific run for failures."""
        resp = requests.get(
            f"{self.host}/api/2.1/jobs/runs/get",
            headers=self.headers,
            params={"run_id": run_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        state = data.get("state", {})
        result_state = state.get("result_state", "")
        life_cycle = state.get("life_cycle_state", "")

        if result_state in ("FAILED", "TIMEDOUT", "CANCELED") or life_cycle == "INTERNAL_ERROR":
            # Identify failed tasks
            failed_tasks = []
            for task in data.get("tasks", []):
                task_state = task.get("state", {})
                if task_state.get("result_state") in ("FAILED", "TIMEDOUT"):
                    failed_tasks.append(task["task_key"])

            job_id = str(data.get("job_id", self.config.databricks.job_id))

            return DetectionResult(
                detected=True,
                failure_type="databricks_job_failure",
                target=f"job:{job_id}/run:{run_id}",
                details={
                    "job_id": job_id,
                    "run_id": str(run_id),
                    "job_name": data.get("run_name", ""),
                    "state": result_state or life_cycle,
                    "state_message": state.get("state_message", ""),
                    "failed_tasks": failed_tasks,
                },
                affected_downstream=[
                    self.config.databricks.gold_daily_summary,
                    self.config.databricks.gold_risk_scores,
                ],
                records_affected=self._estimate_affected_records(data),
                severity="HIGH" if "transform_silver" in failed_tasks else "MEDIUM",
            )

        return DetectionResult(detected=False, failure_type="none")

    def _get_latest_run_id(self, job_id: str) -> Optional[str]:
        """Get the latest run ID for a job."""
        resp = requests.get(
            f"{self.host}/api/2.1/jobs/runs/list",
            headers=self.headers,
            params={"job_id": job_id, "limit": 1, "active_only": False},
            timeout=30,
        )
        resp.raise_for_status()
        runs = resp.json().get("runs", [])
        return str(runs[0]["run_id"]) if runs else None

    def _estimate_affected_records(self, run_data: dict) -> int:
        """Estimate records affected by the failure."""
        # Default estimate based on typical batch size
        return 18420

