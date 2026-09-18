
<p align="center">
  <img src="https://img.icons8.com/fluency/96/shield.png" alt="DisasterZero" width="80" />
</p>

<h1 align="center">DisasterZero</h1>

<p align="center">
  <strong>Automated Disaster Recovery Testing for Databricks + AWS</strong>
</p>

<p align="center">
  <a href="#architecture">Architecture</a> •
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#scenarios">Scenarios</a> •
  <a href="#quality-gate">Quality Gate</a> •
  <a href="#dashboard">Dashboard</a> •
  <a href="#infrastructure">Infrastructure</a> •
  <a href="#testing">Testing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/databricks-unified-FF3621?style=flat-square&logo=databricks&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS-EC2%20|%20S3%20|%20DynamoDB-232F3E?style=flat-square&logo=amazonaws&logoColor=white" />
  <img src="https://img.shields.io/badge/terraform-IaC-7B42BC?style=flat-square&logo=terraform&logoColor=white" />
  <img src="https://img.shields.io/badge/tests-54%20passed-3fb950?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" />
</p>

---

## What is DisasterZero?

DisasterZero is a disaster recovery testing platform that **injects real failures** into Databricks and AWS infrastructure, **automatically detects and recovers** from them, and **measures RTO/RPO compliance** — all without manual intervention.

It answers the question every data team should be asking: *"If our pipeline fails right now, how fast can we recover, and how much data do we lose?"*

### The Problem

Most data teams have no idea what happens when their Databricks jobs fail, clusters terminate unexpectedly, or S3 access is revoked. They find out in production — at 2 AM — when it's already too late.

### The Solution

DisasterZero runs controlled chaos experiments against your data infrastructure:

1. **Simulate** — Inject failures (job cancellations, cluster terminations, data corruption, EC2 stops, S3 blocks)
2. **Detect** — Auto-detect failures via API polling and health checks
3. **Recover** — Execute automated recovery (job reruns, cluster restarts, data rollbacks)
4. **Verify** — Measure actual RTO/RPO against your defined targets
5. **Validate** — Run 14 data quality rules to confirm data integrity post-recovery
6. **Report** — Generate incident reports with full audit trails

---

## Architecture

