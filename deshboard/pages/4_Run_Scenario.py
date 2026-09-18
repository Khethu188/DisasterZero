import streamlit as st
import time

st.set_page_config(page_title="Run Scenario | DisasterZero", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
:root { --bg: #0d1117; --bg2: #161b22; --bg3: #21262d; --border: #30363d; --t1: #e6edf3; --t2: #8b949e; --t3: #484f58; --blue: #58a6ff; --green: #3fb950; --red: #f85149; --orange: #d29922; }
* { font-family: 'Inter', sans-serif; }
.stApp { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--bg2); border-right: 1px solid var(--border); }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMetric"] { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
[data-testid="stMetric"] label { color: var(--t2) !important; font-weight: 600; text-transform: uppercase; font-size: 0.7rem !important; letter-spacing: 0.8px; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--t1) !important; font-weight: 800; }
.section-title { font-size: 0.7rem; font-weight: 700; color: var(--t2); text-transform: uppercase; letter-spacing: 1.2px; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.scenario-detail { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin: 16px 0; }
.scenario-detail:hover { border-color: var(--blue); }
.scenario-name { font-size: 1.1rem; font-weight: 700; color: var(--t1); }
.scenario-desc { font-size: 0.85rem; color: var(--t2); margin-top: 6px; line-height: 1.5; }
.scenario-meta { display: flex; gap: 24px; margin-top: 12px; font-size: 0.8rem; }
.scenario-meta-item { color: var(--t3); }
.scenario-meta-item span { color: var(--t1); font-weight: 600; }
.sev-critical { color: var(--red) !important; }
.sev-high { color: var(--orange) !important; }
.sev-medium { color: var(--blue) !important; }
.stButton > button[kind="primary"] { background: var(--red) !important; color: #fff !important; border: none !important; border-radius: 8px; font-weight: 700; font-size: 0.95rem; padding: 12px; transition: all 0.15s ease; }
.stButton > button[kind="primary"]:hover { opacity: 0.9; }
.stButton > button { background: var(--bg3); color: var(--t1); border: 1px solid var(--border); border-radius: 8px; font-weight: 600; transition: all 0.15s ease; }
.stButton > button:hover { background: var(--blue); color: #fff; border-color: var(--blue); }
.step-row { background: var(--bg2); border-left: 3px solid var(--green); border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 6px 0; display: flex; justify-content: space-between; align-items: center; }
.step-label { font-size: 0.85rem; color: var(--t1); }
.step-label strong { color: var(--green); }
.step-time { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--t3); }
.result-banner { background: rgba(63, 185, 80, 0.08); border: 1px solid rgba(63, 185, 80, 0.2); border-radius: 12px; padding: 24px; text-align: center; margin: 16px 0; }
.result-banner-title { font-size: 1.25rem; font-weight: 800; color: var(--green); }
.result-banner-sub { font-size: 0.85rem; color: var(--t2); margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 32px 0 8px 0;">
    <h1 style="font-size: 2rem; font-weight: 800; color: #e6edf3; letter-spacing: -1px; margin: 0;">Run Scenario</h1>
    <p style="color: #8b949e; margin: 6px 0 0 0;">Simulate infrastructure failures and validate disaster recovery.</p>
</div>
""", unsafe_allow_html=True)

scenarios = {
    "Databricks Job Failure": ("Cancel a running Databricks job to simulate unexpected pipeline failure. Tests detection, automatic re-run, and data verification.", "HIGH", "Databricks Job Pipeline"),
    "Cluster Termination": ("Terminate the active Databricks cluster to simulate infrastructure failure. Tests cluster restart and pipeline continuity.", "CRITICAL", "Databricks Cluster"),
    "Data Corruption": ("Inject corrupt records (NULLs, negatives, invalid codes) into the Silver layer. Tests quality gate detection and quarantine.", "HIGH", "Silver Layer Table"),
    "EC2 Instance Stop": ("Stop the EC2 instance running supporting services. Tests instance restart and health check verification.", "MEDIUM", "EC2 Instance"),
    "S3 Access Denied": ("Apply a deny-all bucket policy to simulate storage access failure. Tests access restoration and data availability.", "HIGH", "S3 Bucket"),
}

st.markdown('<div class="section-title">Select Scenario</div>', unsafe_allow_html=True)

selected = st.selectbox("Scenario", list(scenarios.keys()), label_visibility="collapsed")
desc, sev, target = scenarios[selected]
sev_class = f"sev-{sev.lower()}"

st.markdown(f"""
<div class="scenario-detail">
    <div class="scenario-name">{selected}</div>
    <div class="scenario-desc">{desc}</div>
    <div class="scenario-meta">
        <div class="scenario-meta-item">Target: <span>{target}</span></div>
        <div class="scenario-meta-item">Severity: <span class="{sev_class}">{sev}</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-title">Configuration</div>', unsafe_allow_html=True)

cc1, cc2 = st.columns(2)
with cc1:
    safety = st.toggle("Safety Mode", value=True, help="Auto-cleanup after scenario")
with cc2:
    dry_run = st.toggle("Dry Run", value=True, help="Simulate without real changes")

st.markdown('<div class="section-title">Execute</div>', unsafe_allow_html=True)

if dry_run:
    st.caption("Dry run mode: no actual failures will be injected.")

if st.button("Launch Scenario", type="primary", use_container_width=True):
    if dry_run:
        with st.status("Executing scenario...", expanded=True) as status:
            st.write("Initializing simulator...")
            time.sleep(0.4)
            st.write(f"Target: {target}")
            time.sleep(0.3)
            st.write("Injecting failure (simulated)...")
            bar = st.progress(0)
            for i in range(100):
                time.sleep(0.008)
                bar.progress(i + 1)
            st.write("Failure detected")
            time.sleep(0.3)
            st.write("Executing recovery...")
            time.sleep(0.4)
            st.write("Verifying RTO/RPO...")
            time.sleep(0.3)
            st.write("Generating report...")
            time.sleep(0.2)
            status.update(label="Complete", state="complete")

        st.markdown("""
        <div class="result-banner">
            <div class="result-banner-title">SCENARIO PASSED</div>
            <div class="result-banner-sub">All recovery targets met</div>
        </div>
        """, unsafe_allow_html=True)

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Status", "PASSED")
        with r2:
            st.metric("RTO", "12.4s")
        with r3:
            st.metric("Records Lost", "0")
        with r4:
            st.metric("Duration", "1.8s")

        steps = [
            ("Step 1", "Failure injected", "0.4s"),
            ("Step 2", "Failure detected via API", "2.1s"),
            ("Step 3", "Recovery executed", "8.7s"),
            ("Step 4", "RTO/RPO verified", "1.2s"),
            ("Step 5", "Report generated", "0.4s"),
        ]
        for label, detail, dur in steps:
            st.markdown(f"""
            <div class="step-row">
                <div class="step-label"><strong>{label}</strong> &mdash; {detail}</div>
                <div class="step-time">{dur}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        st.info("Disable Dry Run to execute against real infrastructure.")
    else:
        st.error("Live mode requires Databricks and AWS credentials in your .env file.")
        st.code("DATABRICKS_HOST=https://your-workspace.cloud.databricks.com\nDATABRICKS_TOKEN=your-token\nAWS_REGION=af-south-1\nEC2_INSTANCE_ID=i-your-instance", language="bash")

st.markdown("""
<div style="text-align: center; color: #484f58; padding: 40px 0 20px 0; font-size: 0.8rem; border-top: 1px solid #30363d; margin-top: 48px;">
    DisasterZero v1.0 &middot; Run Scenario
</div>
""", unsafe_allow_html=True)
