#!/usr/bin/env python3
"""
Web Dashboard for crash visualization - Streamlit
"""

# IMPORTANT: These imports must come FIRST
import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# ← ADD THESE LINES to define paths (BEFORE set_page_config)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
pc_tools_path = os.path.join(parent_dir, 'pc_tools')
sys.path.insert(0, pc_tools_path)

# NOW set_page_config (first Streamlit call)
st.set_page_config(
    page_title="CoreDump Dashboard - ACTIA PFE",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import database module (after path is defined)
from pc_tools.database import CrashDatabase

# ← The rest of your code can continue here...
st.title("🚨 CoreDump Dashboard - ACTIA PFE")
st.markdown("---")

# Database initialization
@st.cache_resource
def get_database():
    # Database file path
    db_path = os.path.join(parent_dir, 'crash_dumps.db')
    return CrashDatabase(db_path)

# ... rest of existing code
try:
    db = get_database()
    crashes = db.get_all_crashes()
except Exception as e:
    st.error(f"Database connection error: {e}")
    crashes = []

# Sidebar - Filters
st.sidebar.header("🔍 Filters")
severity_filter = st.sidebar.multiselect(
    "Severity",
    options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    default=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
)

# Main metrics
st.header("📊 Overview")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Crashes", value=len(crashes))

with col2:
    critical_count = len([c for c in crashes if c.get('severity') == 'CRITICAL']) if crashes else 0
    st.metric(label="Critical Crashes", value=critical_count)

with col3:
    st.metric(label="Last Crash", 
              value=crashes[0]['timestamp'] if crashes else "N/A")

st.markdown("---")

# Crashes table
st.header("📋 Crashes List")

if crashes:
    df = pd.DataFrame(crashes)
    
    # Apply severity filter
    if severity_filter:
        df = df[df['severity'].isin(severity_filter)]
    
    # Display table
    st.dataframe(df, use_container_width=True)
    
    # CSV Export
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Export as CSV",
        data=csv,
        file_name=f"crashes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
else:
    st.info("No crashes recorded in the database")

st.markdown("---")
st.caption("CoreDump Dashboard - ACTIA PFE 2024")