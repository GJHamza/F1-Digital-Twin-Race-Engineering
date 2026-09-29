# -*- coding: utf-8 -*-
"""
F1 Digital Twin — Race Engineering Platform Analytics Dashboard.
Provides a professional, high-density, dual-tab motorsport engineering interface:
- Tab 1: Race Strategy Engineering (G.4.5 Optimization Ranking, Stint Timeline, Trade-offs, Fuel/Tires, Validation Audit)
- Tab 2: Real-Time Telemetry & Cockpit (4-Corner Wheel Status, Radar Performance Index, GPS Track Analysis, Setup Advisor)
"""

import math
import os
import sys
import json
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure code directory and project root are added to sys.path for Streamlit runtime execution
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for path in [CODE_DIR, PROJECT_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env'))

# Streamlit Page Configuration
st.set_page_config(
    page_title="F1 Digital Twin — Race Engineering Platform",
    layout="wide",
    page_icon="⚙️",
    initial_sidebar_state="expanded",
)

# Professional High-Contrast Motorsport Visual Style
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Inter:wght@400;600;700;800&display=swap');
    
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers & Title */
    h1, h2, h3, h4 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    .dashboard-header-container {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-left: 6px solid #0066ff;
        border-radius: 8px;
        padding: 18px 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    
    .dashboard-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        letter-spacing: 0.5px;
    }
    
    .dashboard-subtitle {
        font-size: 0.85rem;
        color: #94a3b8;
        font-family: 'JetBrains Mono', monospace;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Engineering Cards */
    .eng-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    
    .metric-card-custom {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        border-top: 4px solid #0066ff;
    }
    
    .metric-title {
        color: #94a3b8;
        font-size: 0.72rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-val {
        font-size: 1.9rem;
        font-weight: 800;
        color: #ffffff;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1.1;
    }
    
    .metric-unit {
        font-size: 0.9rem;
        color: #64748b;
        font-weight: 400;
    }

    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-valid { background-color: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }
    .badge-warning { background-color: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    .badge-invalid { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    
    /* Sidebar Styling */
    .stSidebar {
        background-color: #0f172a !important;
        border-right: 1px solid #334155 !important;
    }
    
    /* Streamlit Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #0f172a;
        padding: 4px;
        border-bottom: 1px solid #334155;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px 6px 0 0;
        color: #94a3b8;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0066ff !important;
        color: #ffffff !important;
        border-color: #0066ff !important;
    }
    
    /* Wireframe Tyre light layout */
    .car-wireframe-dark {
        position: relative;
        width: 170px;
        height: 270px;
        margin: 15px auto;
        border: 2px solid #334155;
        border-radius: 24px 24px 8px 8px;
        background: #1e293b;
    }
    .car-body-wire-dark {
        position: absolute;
        top: 22%;
        left: 35%;
        width: 30%;
        height: 56%;
        border: 2px solid #475569;
        border-radius: 8px;
        background: #0f172a;
    }
    .tire-block-dark {
        position: absolute;
        width: 36px;
        height: 54px;
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        font-size: 0.65rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .tire-fl { top: 10%; left: -18px; }
    .tire-fr { top: 10%; right: -18px; }
    .tire-rl { bottom: 10%; left: -18px; }
    .tire-rr { bottom: 10%; right: -18px; }
    </style>
""", unsafe_allow_html=True)

# Connexion MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')

@st.cache_resource
def init_connection():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000, connectTimeoutMS=1000, socketTimeoutMS=1000)
        client.admin.command('ping')
        return client
    except Exception:
        return None

client = init_connection()

# Sidebar Navigation & System Status
st.sidebar.markdown("### F1 DIGITAL TWIN")
st.sidebar.markdown("**Race Engineering Suite**")
st.sidebar.markdown("---")

is_offline = False
if not client:
    is_offline = True
    st.sidebar.markdown("<span class='status-badge badge-warning'>DATABASE OFFLINE</span>", unsafe_allow_html=True)
    st.sidebar.caption("Running with local simulation & telemetry fallback.")
    col_telemetry = None
    col_settings = None
else:
    st.sidebar.markdown("<span class='status-badge badge-valid'>DATABASE CONNECTED</span>", unsafe_allow_html=True)
    db = client['F1_Simulation']
    col_telemetry = db['telemetry']
    col_settings = db['car_settings']

st.sidebar.markdown("---")
st.sidebar.markdown("**SESSION INFO**")
st.sidebar.caption("Vehicle: Williams FW45 Digital Twin")
st.sidebar.caption("Circuit: Grand Prix Circuit")
st.sidebar.caption("Config: 52 Laps / 110 kg Fuel")

# Load telemetry data helper
def load_data():
    if is_offline:
        now = datetime.now()
        timestamps = [now - pd.Timedelta(seconds=i) for i in range(250, 0, -1)]
        speeds = [220 + 80 * np.sin(i/15) + np.random.normal(0, 3) for i in range(250)]
        gforces = [1.2 + 0.9 * np.cos(i/12) + np.random.normal(0, 0.04) for i in range(250)]
        torques = [450 + 120 * np.sin(i/15) for i in range(250)]
        wear_fl = [min(100, 10 + i*0.06) for i in range(250)]
        wear_fr = [min(100, 8 + i*0.06) for i in range(250)]
        wear_rl = [min(100, 5 + i*0.05) for i in range(250)]
        wear_rr = [min(100, 6 + i*0.05) for i in range(250)]
        pos_x = [120 * np.sin(i/20) for i in range(250)]
        pos_z = [90 * np.cos(i/20) for i in range(250)]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'speed': speeds,
            'g_force': gforces,
            'torque': torques,
            'tire_wear': list(zip(wear_fl, wear_fr, wear_rl, wear_rr)),
            'pos_x': pos_x,
            'pos_z': pos_z
        })
        return df
        
    try:
        cursor = col_telemetry.find({"ping": {"$exists": False}}).sort('_id', -1).limit(1000)
        data = list(cursor)
        if not data: 
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
        
        for col in ['speed', 'g_force', 'torque', 'pos_x', 'pos_z']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            else:
                df[col] = 0.0
        
        return df
    except Exception:
        return pd.DataFrame()

# Strategy Engineering Adapter Initialization Helper
def get_strategy_adapter():
    if "strategy_adapter" in st.session_state and st.session_state["strategy_adapter"] is not None:
        return st.session_state["strategy_adapter"]
    try:
        from ml.strategy import (
            OptimizationConfig, OptimizationCandidate, StrategyOptimizer, StrategyDashboardAdapter
        )
        cands = [
            OptimizationCandidate("SCN_001", "SOFT:1-25|MEDIUM:26-52", True, 0, 4800.0, 1, 5.2, 35.0),
            OptimizationCandidate("SCN_002", "MEDIUM:1-28|HARD:29-52", True, 0, 4812.5, 1, 8.0, 28.0),
            OptimizationCandidate("SCN_003", "SOFT:1-18|MEDIUM:19-36|HARD:37-52", True, 1, 4835.0, 2, 4.5, 22.0),
            OptimizationCandidate("SCN_004", "HARD:1-32|MEDIUM:33-52", True, 0, 4850.2, 1, 10.1, 30.0),
            OptimizationCandidate("SCN_005", "MEDIUM:1-20|SOFT:21-38|SOFT:39-52", True, 1, 4870.0, 2, 3.8, 42.0),
        ]
        opt = StrategyOptimizer(OptimizationConfig(top_k=5))
        ranking = opt.optimize(cands)
        adapter = StrategyDashboardAdapter(ranking_result=ranking)
        st.session_state["strategy_adapter"] = adapter
        return adapter
    except Exception as ex:
        st.error(f"Error loading strategy engine: {ex}")
        return None

# Header Banner
st.markdown("""
    <div class="dashboard-header-container">
        <div class="dashboard-title">F1 DIGITAL TWIN — RACE ENGINEERING PLATFORM</div>
        <div class="dashboard-subtitle">WILLIAMS FW45 TELEMETRY & STRATEGY ANALYSIS SUITE</div>
    </div>
""", unsafe_allow_html=True)

# Main Navigation Tabs
tab_strategy, tab_telemetry = st.tabs(["RACE STRATEGY ENGINEERING", "REAL-TIME TELEMETRY & COCKPIT"])

# ============================================================
# TAB 1: RACE STRATEGY ENGINEERING
# ============================================================
with tab_strategy:
    adapter = get_strategy_adapter()
    if adapter is None or adapter.ranking_result.is_empty:
        st.warning("No strategy optimization payload available.")
    else:
        from ml.strategy.strategy_dashboard import render_strategy_dashboard_tab
        render_strategy_dashboard_tab(adapter)

# ============================================================
# TAB 2: REAL-TIME TELEMETRY & COCKPIT
# ============================================================
with tab_telemetry:
    df = load_data()

    def clean_num(val, default=0.0):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)

    if df.empty:
        st.warning("AWAITING VEHICLE SIMULATION STREAM...")
    else:
        latest = df.iloc[-1]
        speed = clean_num(latest.get('speed'), 0.0)
        gforce = clean_num(latest.get('g_force'), 1.0)
        torque = clean_num(latest.get('torque'), 0.0)
        wear = latest.get('tire_wear', [0.0, 0.0, 0.0, 0.0])
        if not isinstance(wear, (list, tuple)) or len(wear) < 4:
            wear = [0.0, 0.0, 0.0, 0.0]
        wear = [clean_num(w, 0.0) for w in wear]

        top_speed = clean_num(df['speed'].max(), 0.0)
        max_torque = clean_num(df['torque'].max(), 0.0)
        max_g = clean_num(df['g_force'].max(), 1.0)

        # 1. Metric Cards Row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
                <div class='metric-card-custom'>
                    <div class='metric-title'>CURRENT SPEED / TOP</div>
                    <div class='metric-val'>{speed:.0f} <span style='font-size:1.1rem;color:#64748b'>/ {top_speed:.0f}</span> <span class='metric-unit'>km/h</span></div>
                </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
                <div class='metric-card-custom' style='border-top-color:#f59e0b'>
                    <div class='metric-title'>G-FORCE LIVE / MAX</div>
                    <div class='metric-val'>{gforce:.2f} <span style='font-size:1.1rem;color:#64748b'>/ {max_g:.2f}</span> <span class='metric-unit'>G</span></div>
                </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
                <div class='metric-card-custom' style='border-top-color:#22c55e'>
                    <div class='metric-title'>TORQUE / PEAK</div>
                    <div class='metric-val'>{torque:.0f} <span style='font-size:1.1rem;color:#64748b'>/ {max_torque:.0f}</span> <span class='metric-unit'>Nm</span></div>
                </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
                <div class='metric-card-custom' style='border-top-color:#ef4444'>
                    <div class='metric-title'>AVG TIRE WEAR</div>
                    <div class='metric-val'>{sum(wear)/4:.1f} <span class='metric-unit'>%</span></div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. Main Analytics Panel Grid
        col_vis, col_radar, col_track = st.columns([1.1, 1.4, 1.5])
        
        with col_vis:
            st.markdown("#### TYRE STATUS & TELEMETRY")
            
            def get_tire_color(w):
                if w > 65: return "#ef4444"
                if w > 30: return "#f59e0b"
                return "#0066ff"

            temps = [90 + (w * 0.4) for w in wear]
            pressures = [22.0 + (w * 0.04) for w in wear]

            wireframe_html = f"""
            <div class="car-wireframe-dark">
                <div class="car-body-wire-dark"></div>
                <div class="tire-block-dark tire-fl" style="background:{get_tire_color(wear[0])}">FL<br>{temps[0]:.0f}°C<br>{pressures[0]:.1f}p</div>
                <div class="tire-block-dark tire-fr" style="background:{get_tire_color(wear[1])}">FR<br>{temps[1]:.0f}°C<br>{pressures[1]:.1f}p</div>
                <div class="tire-block-dark tire-rl" style="background:{get_tire_color(wear[2])}">RL<br>{temps[2]:.0f}°C<br>{pressures[2]:.1f}p</div>
                <div class="tire-block-dark tire-rr" style="background:{get_tire_color(wear[3])}">RR<br>{temps[3]:.0f}°C<br>{pressures[3]:.1f}p</div>
            </div>
            """
            st.markdown(wireframe_html, unsafe_allow_html=True)
            wear_diff = abs(wear[0] - wear[2])
            status_txt = "Nominal tire degradation profile."
            if wear[0] > 50 or wear[1] > 50:
                status_txt = "Critical wear on front axle. Consider wing downforce adjustment."
            elif wear_diff > 15:
                status_txt = "Asymmetric wear bias detected."
            st.caption(f"Tyre Report: {status_txt} Avg Temp: {sum(temps)/4:.0f}°C")

        with col_radar:
            st.markdown("#### VEHICLE PERFORMANCE INDEX")
            agility = min(100, (gforce / 3.2) * 100)
            top_s = min(100, (top_speed / 350) * 100)
            stability = max(0, 100 - (gforce * 8))
            stamina = max(0, 100 - sum(wear)/4)
            power = min(100, (max_torque / 900) * 100)
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=[agility, top_s, power, stability, stamina, agility],
                theta=['Agility', 'Top Speed', 'Power', 'Stability', 'Stamina', 'Agility'],
                fill='toself',
                name='Performance Profile',
                line=dict(color='#0066ff', width=2),
                fillcolor='rgba(0, 102, 255, 0.2)'
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor='#334155', linecolor='#334155', tickfont=dict(size=8, color='#94a3b8')),
                    angularaxis=dict(gridcolor='#334155', linecolor='#334155', tickfont=dict(size=10, color='#f8fafc')),
                    bgcolor='rgba(15, 23, 42, 0.4)'
                ),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=10, b=10),
                height=260,
                showlegend=False
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_track:
            st.markdown("#### GPS TRACK ANALYSIS")
            if 'pos_x' in df.columns and 'pos_z' in df.columns:
                fig_track = px.scatter(
                    df, 
                    x='pos_x', 
                    y='pos_z', 
                    color='speed', 
                    color_continuous_scale='Blues',
                    labels={'speed': 'Speed (km/h)'}
                )
                fig_track.update_traces(marker=dict(size=5, opacity=0.85))
                fig_track.add_trace(go.Scatter(
                    x=[df['pos_x'].iloc[-1]], 
                    y=[df['pos_z'].iloc[-1]], 
                    mode='markers', 
                    marker=dict(size=12, color='#ef4444', symbol='cross', line=dict(color='#ffffff', width=2)),
                    name='Live Pos'
                ))
                fig_track.update_layout(
                    plot_bgcolor='#1e293b',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#f8fafc',
                    xaxis=dict(showgrid=False, zeroline=False, visible=False),
                    yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=260,
                    showlegend=False
                )
                st.plotly_chart(fig_track, use_container_width=True)
            else:
                st.info("Awaiting GPS coordinates...")

        # 3. Telemetry Stream Timeline
        st.markdown("#### TELEMETRY STREAMS TIMELINE")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['speed'],
            mode='lines',
            name='Speed (km/h)',
            line=dict(color='#0066ff', width=2)
        ))
        fig_line.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['torque'],
            mode='lines',
            name='Torque (Nm)',
            line=dict(color='#22c55e', width=2),
            yaxis='y2'
        ))
        fig_line.update_layout(
            plot_bgcolor='#1e293b',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=30, r=30, t=10, b=10),
            xaxis=dict(showgrid=True, gridcolor='#334155', tickfont=dict(size=9, color='#94a3b8')),
            yaxis=dict(title=dict(text='Speed (km/h)', font=dict(color='#0066ff', size=10)), tickfont=dict(color='#0066ff', size=8), showgrid=True, gridcolor='#334155'),
            yaxis2=dict(title=dict(text='Torque (Nm)', font=dict(color='#22c55e', size=10)), tickfont=dict(color='#22c55e', size=8), overlaying='y', side='right', showgrid=False),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(color='#f8fafc', size=10)),
            height=200
        )
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("---")

        # 4. Setup Advisor & Onboard Tuning Panel
        st.markdown("#### SETUP ADVISOR & TUNING CONTROL")
        cg1, cg2 = st.columns(2)
        with cg1:
            aero = st.slider("Downforce Setup (Wing angle)", 0, 100, 50)
        with cg2:
            engine = st.slider("Engine aggressiveness fuel mix", 1, 10, 5)

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("SYNC SETUP TO VEHICLE"):
                if is_offline:
                    st.info("Simulation Mode: configuration logged.")
                else:
                    col_settings.insert_one({"timestamp": datetime.now().isoformat(), "downforce": aero, "engine_mix": engine})
                    st.success("Setup successfully synced with vehicle onboard telemetry.")

        with c_btn2:
            report = {
                "max_gforce": float(max_g),
                "top_speed": float(top_speed),
                "tire_wear": [float(w) for w in wear],
                "setup": {"downforce": aero, "engine": engine}
            }
            st.download_button("EXPORT TELEMETRY JSON", data=json.dumps(report, indent=4), file_name="f1_telemetry_export.json", mime="application/json")

        if not is_offline:
            import time
            time.sleep(1.5)
            st.rerun()
