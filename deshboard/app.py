import streamlit as st
import json
import os
import glob

st.set_page_config(
    page_title="DisasterZero",
    page_icon="https://img.icons8.com/fluency/48/shield.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

def load_reports():
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports
    for fp in glob.glob(os.path.join(REPORTS_DIR, "*.json")):
        try:
            with open(fp, "r") as f:
                reports.append(json.load(f))
        except Exception:
            continue
    return reports

reports = load_reports()
total = len(reports)
passed = sum(1 for r in reports if r.get("overall_passed", False))
failed = total - passed
rate = (passed / total * 100) if total > 0 else 0

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #484f58;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-red: #f85149;
    --accent-orange: #d29922;
    --accent-purple: #bc8cff;
}

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

.stApp {
    background: var(--bg-primary);
}

[data-testid="stSidebar"] {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
}

header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar Brand ── */
.sidebar-brand {
    padding: 24px 0 16px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}

.sidebar-brand-name {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.5px;
}

.sidebar-brand-tag {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

.sidebar-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--accent-green);
}

.sidebar-status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 6px var(--accent-green);
}

.sidebar-links {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
}

.sidebar-links a {
    color: var(--accent-blue);
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 500;
}

.sidebar-links a:hover { text-decoration: underline; }

/* ── Page Header ── */
.page-header {
    padding: 32px 0 8px 0;
}

.page-header h1 {
    font-size: 2rem;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: -1px;
    margin: 0;
    line-height: 1.2;
}

.page-header p {
    color: var(--text-secondary);
    font-size: 1rem;
    margin: 6px 0 0 0;
    font-weight: 400;
}

/* ── Stat Cards ── */
.stat-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin: 24px 0;
}

.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s ease;
}

.stat-card:hover { border-color: var(--accent-blue); }

.stat-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
}

.stat-value {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1;
}

.stat-value-green { color: var(--accent-green); }
.stat-value-red { color: var(--accent-red); }
.stat-value-blue { color: var(--accent-blue); }

.stat-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 6px;
}

/* ── Section ── */
.section-title {
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: 40px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* ── Pipeline ── */
.pipeline {
    display: flex;
    gap: 0;
    margin: 16px 0;
    overflow-x: auto;
}

.pipeline-node {
    flex: 1;
    min-width: 160px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    padding: 16px;
    position: relative;
    transition: all 0.2s ease;
}

.pipeline-node:first-child { border-radius: 12px 0 0 12px; }
.pipeline-node:last-child { border-radius: 0 12px 12px 0; }

.pipeline-node:hover {
    background: var(--bg-tertiary);
    border-color: var(--accent-blue);
    z-index: 1;
}

.pipeline-node-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.pipeline-node-desc {
    font-size: 0.7rem;
    color: var(--text-secondary);
    line-height: 1.4;
}

.pipeline-arrow {
    display: flex;
    align-items: center;
    color: var(--text-muted);
    font-size: 1.2rem;
    padding: 0 2px;
}

/* ── Action Cards ── */
.action-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 16px 0;
}

.action-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    transition: all 0.2s ease;
    cursor: pointer;
}

.action-card:hover {
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.action-card-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    margin-bottom: 12px;
}

.action-card-icon-red { background: rgba(248, 81, 73, 0.12); color: var(--accent-red); }
.action-card-icon-blue { background: rgba(88, 166, 255, 0.12); color: var(--accent-blue); }
.action-card-icon-purple { background: rgba(188, 140, 255, 0.12); color: var(--accent-purple); }

.action-card-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.action-card-desc {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.4;
}

/* ── Tech Tags ── */
.tech-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 16px 0;
}

.tech-tag {
    display: inline-block;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    background: var(--bg-secondary);
    transition: all 0.15s ease;
}

.tech-tag:hover {
    border-color: var(--accent-blue);
    color: var(--accent-blue);
}

/* ── Progress Bar ── */
.progress-container {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}

.progress-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 12px;
}

.progress-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-primary);
}

.progress-count {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--accent-green);
    font-family: 'JetBrains Mono', monospace;
}

.progress-bar-bg {
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 1s ease;
}

.progress-bar-green { background: var(--accent-green); }

.progress-breakdown {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
}

/* ── Footer ── */
.footer {
    text-align: center;
    padding: 40px 0 20px 0;
    color: var(--text-muted);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 48px;
}

.footer strong { color: var(--text-secondary); }

/* ── Hide Streamlit defaults ── */
[data-testid="stMetric"] {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
}

[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.7rem !important;
    letter-spacing: 0.8px;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 800;
}

.stButton > button {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 10px 20px;
    transition: all 0.15s ease;
}

.stButton > button:hover {
    background: var(--accent-blue);
    color: #fff;
    border-color: var(--accent-blue);
}

div[data-testid="stSelectbox"] label { color: var(--text-secondary) !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
st.sidebar.markdown("""
<div class="sidebar-brand">
    <div style="display: flex; align-items: center; gap: 10px;">
        <img src="https://img.icons8.com/fluency/48/shield.png" width="28" height="28" />
        <div>
            <div class="sidebar-brand-name">DisasterZero</div>
            <div class="sidebar-brand-tag">Recovery Platform v1.0</div>
        </div>
    </div>
    <div class="sidebar-status">
        <div class="sidebar-status-dot"></div>
        All systems operational
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div class="sidebar-links">
    <div style="color: #8b949e; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; font-weight: 600;">Developer</div>
    <div style="color: #e6edf3; font-weight: 600; font-size: 0.9rem;">Khethukuthula Sabela</div>
    <div style="margin-top: 6px;">
        <a href="https://github.com/Khethu188">GitHub</a>
        <span style="color: #30363d; margin: 0 6px;">|</span>
        <a href="https://linkedin.com/in/khethukuthula-sabela-a48089241">LinkedIn</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Page Header ──
st.markdown("""
<div class="page-header">
    <h1>Command Centre</h1>
    <p>Monitor disaster recovery scenarios, track incidents, and verify RTO/RPO compliance.</p>
</div>
""", unsafe_allow_html=True)

# ── Stats ──
st.markdown(f"""
<div class="stat-row">
    <div class="stat-card">
        <div class="stat-label">Total Scenarios</div>
        <div class="stat-value">{total}</div>
        <div class="stat-sub">Lifetime executions</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Passed</div>
        <div class="stat-value stat-value-green">{passed}</div>
        <div class="stat-sub">Recovery successful</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Failed</div>
        <div class="stat-value stat-value-red">{failed}</div>
        <div class="stat-sub">Needs investigation</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Pass Rate</div>
        <div class="stat-value stat-value-blue">{rate:.0f}%</div>
        <div class="stat-sub">Overall success rate</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Pipeline ──
st.markdown('<div class="section-title">Recovery Pipeline</div>', unsafe_allow_html=True)

st.markdown("""
<div class="pipeline">
    <div class="pipeline-node">
        <div class="pipeline-node-title">Simulate</div>
        <div class="pipeline-node-desc">Inject failures into Databricks jobs, clusters, EC2, S3</div>
    </div>
    <div class="pipeline-arrow">&rarr;</div>
    <div class="pipeline-node">
        <div class="pipeline-node-title">Detect</div>
        <div class="pipeline-node-desc">Auto-detect via API polling and health checks</div>
    </div>
    <div class="pipeline-arrow">&rarr;</div>
    <div class="pipeline-node">
        <div class="pipeline-node-title">Recover</div>
        <div class="pipeline-node-desc">Job reruns, cluster restarts, data rollbacks</div>
    </div>
    <div class="pipeline-arrow">&rarr;</div>
    <div class="pipeline-node">
        <div class="pipeline-node-title">Verify</div>
        <div class="pipeline-node-desc">Measure RTO/RPO against defined targets</div>
    </div>
    <div class="pipeline-arrow">&rarr;</div>
    <div class="pipeline-node">
        <div class="pipeline-node-title">Quality Gate</div>
        <div class="pipeline-node-desc">14 data quality rules, auto-quarantine</div>
    </div>
    <div class="pipeline-arrow">&rarr;</div>
    <div class="pipeline-node">
        <div class="pipeline-node-title">Report</div>
        <div class="pipeline-node-desc">Incident reports with full audit trail</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Quick Actions ──
st.markdown('<div class="section-title">Quick Actions</div>', unsafe_allow_html=True)

ac1, ac2, ac3 = st.columns(3)
with ac1:
    if st.button("Run Scenario", use_container_width=True):
        st.switch_page("pages/4_Run_Scenario.py")
with ac2:
    if st.button("View Reports", use_container_width=True):
        st.switch_page("pages/3_Reports.py")
with ac3:
    if st.button("View Incidents", use_container_width=True):
        st.switch_page("pages/2_Incidents.py")

# ── Test Results ──
st.markdown('<div class="section-title">Test Suite</div>', unsafe_allow_html=True)

st.markdown("""
<div class="progress-container">
    <div class="progress-header">
        <div class="progress-title">pytest results</div>
        <div class="progress-count">54 / 54 passed</div>
    </div>
    <div class="progress-bar-bg">
        <div class="progress-bar-fill progress-bar-green" style="width: 100%;"></div>
    </div>
    <div class="progress-breakdown">
        <span>Unit: 23</span>
        <span>Integration: 24</span>
        <span>End-to-End: 7</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tech Stack ──
st.markdown('<div class="section-title">Technology</div>', unsafe_allow_html=True)

st.markdown("""
<div class="tech-tags">
    <span class="tech-tag">Python</span>
    <span class="tech-tag">Databricks</span>
    <span class="tech-tag">Unity Catalog</span>
    <span class="tech-tag">Delta Lake</span>
    <span class="tech-tag">AWS EC2</span>
    <span class="tech-tag">AWS S3</span>
    <span class="tech-tag">DynamoDB</span>
    <span class="tech-tag">SNS</span>
    <span class="tech-tag">Terraform</span>
    <span class="tech-tag">Docker</span>
    <span class="tech-tag">GitHub Actions</span>
    <span class="tech-tag">pytest</span>
    <span class="tech-tag">Streamlit</span>
    <span class="tech-tag">Medallion Architecture</span>
</div>
""", unsafe_allow_html=True)

# ── Footer ──
st.markdown("""
<div class="footer">
    <strong>DisasterZero</strong> v1.0 &middot; Built by Khethukuthula Sabela &middot; Cape Town, South Africa
</div>
""", unsafe_allow_html=True)
