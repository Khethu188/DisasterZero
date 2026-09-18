
"""
scripts/smoke_test.py
─────────────────────
Post-deployment smoke tests for DisasterZero.
Validates that all infrastructure components are healthy.

Usage:
    python scripts/smoke_test.py --environment dev --outputs deployment-outputs.json
"""

import argparse
import json
import sys
import time

import boto3
import requests


class SmokeTestRunner:
    """Run post-deployment smoke tests."""

    def __init__(self, environment: str, outputs: dict):
        self.environment = environment
        self.outputs = outputs
        self.results = []
        self.ec2 = boto3.client("ec2")
        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.client("dynamodb")
        self.cloudwatch = boto3.client("cloudwatch")
        self.lambda_client = boto3.client("lambda")

    def run_all(self) -> bool:
        """Run all smoke tests. Returns True if all pass."""
        print("\n🛡️  DisasterZero — Smoke Tests")
        print(f"   Environment: {self.environment}")
        print("=" * 50)

        tests = [
            ("EC2 Instance Running", self.test_ec2_running),
            ("S3 Bucket Accessible", self.test_s3_accessible),
            ("S3 Folder Structure", self.test_s3_folders),
            ("DynamoDB Table Active", self.test_dynamodb_active),
            ("Lambda Function Ready", self.test_lambda_ready),
            ("CloudWatch Alarms Set", self.test_cloudwatch_alarms),
            ("Streamlit Dashboard Up", self.test_dashboard_reachable),
            ("Databricks Connectivity", self.test_databricks_api),
        ]

        for name, test_fn in tests:
            try:
                result = test_fn()
                status = "✅ PASS" if result else "❌ FAIL"
                self.results.append({"name": name, "passed": result})
                print(f"  {status}  {name}")
            except Exception as e:
                self.results.append({"name": name, "passed": False, "error": str(e)})
                print(f"  ❌ FAIL  {name} — {e}")

        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        all_passed = passed == total

        print("=" * 50)
        print(f"  Results: {passed}/{total} passed")
        print(f"  Status: {'✅ ALL CLEAR' if all_passed else '❌ ISSUES DETECTED'}")
        print()

        return all_passed

    def test_ec2_running(self) -> bool:
        """Verify EC2 instance is running."""
        instance_id = self.outputs.get("app_instance_id", {}).get("value")
        if not instance_id:
            return False

        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
        return state == "running"

    def test_s3_accessible(self) -> bool:
        """Verify S3 bucket is accessible."""
        bucket = self.outputs.get("data_bucket_name", {}).get("value")
        if not bucket:
            return False

        self.s3.head_bucket(Bucket=bucket)
        return True

    def test_s3_folders(self) -> bool:
        """Verify S3 folder structure exists."""
        bucket = self.outputs.get("data_bucket_name", {}).get("value")
        if not bucket:
            return False

        expected_prefixes = ["raw/", "processed/", "quarantine/", "reports/", "backups/"]
        response = self.s3.list_objects_v2(Bucket=bucket, Delimiter="/")
        prefixes = [p["Prefix"] for p in response.get("CommonPrefixes", [])]

        return all(p in prefixes for p in expected_prefixes)

    def test_dynamodb_active(self) -> bool:
        """Verify DynamoDB incidents table is active."""
        table_name = f"disasterzero-{self.environment}-incidents"
        response = self.dynamodb.describe_table(TableName=table_name)
        return response["Table"]["TableStatus"] == "ACTIVE"

    def test_lambda_ready(self) -> bool:
        """Verify Lambda recovery function is ready."""
        func_name = f"disasterzero-{self.environment}-recovery"
        response = self.lambda_client.get_function(FunctionName=func_name)
        state = response["Configuration"]["State"]
        return state == "Active"

    def test_cloudwatch_alarms(self) -> bool:
        """Verify CloudWatch alarms are configured."""
        prefix = f"disasterzero-{self.environment}"
        response = self.cloudwatch.describe_alarms(AlarmNamePrefix=prefix)
        alarms = response.get("MetricAlarms", [])
        return len(alarms) >= 4  # At least 4 alarms expected

    def test_dashboard_reachable(self) -> bool:
        """Verify Streamlit dashboard is reachable."""
        instance_id = self.outputs.get("app_instance_id", {}).get("value")
        if not instance_id:
            return False

        # Get public IP
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        ip = response["Reservations"][0]["Instances"][0].get("PublicIpAddress")
        if not ip:
            return False

        try:
            resp = requests.get(f"http://{ip}:8501", timeout=10)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def test_databricks_api(self) -> bool:
        """Verify Databricks API is reachable."""
        import os

        host = os.environ.get("DATABRICKS_HOST", "")
        token = os.environ.get("DATABRICKS_TOKEN", "")
        if not host or not token:
            return True  # Skip if not configured

        try:
            resp = requests.get(
                f"{host}/api/2.0/clusters/list",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            return resp.status_code in (200, 403)  # 403 = auth works, no perms
        except requests.exceptions.RequestException:
            return False


def main():
    parser = argparse.ArgumentParser(description="DisasterZero Smoke Tests")
    parser.add_argument("--environment", required=True, help="Target environment")
    parser.add_argument("--outputs", required=True, help="Path to deployment outputs JSON")
    args = parser.parse_args()

    with open(args.outputs) as f:
        outputs = json.load(f)

    runner = SmokeTestRunner(args.environment, outputs)
    success = runner.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

