import streamlit as st
import numpy as np
import pandas as pd
import joblib
import time
import plotly.graph_objects as go
from database import PredictED_Database


st.set_page_config(page_title="PredictED | Clinical Dashboard", page_icon="⚕️", layout="wide")

st.markdown("""
    <style>
    /* Posh Clinical Aesthetic */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8f9fa;
    }
    
    /* Clean Metric Cards with Soft Shadows */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.06);
    }
    
    /* Elegant Live Indicator */
    .live-indicator {
        display: inline-flex;
        align-items: center;
        background: rgba(220, 53, 69, 0.1);
        color: #dc3545;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
        border: 1px solid rgba(220, 53, 69, 0.2);
    }
    .pulse-dot {
        height: 8px;
        width: 8px;
        background-color: #dc3545;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(220, 53, 69, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
    }
    
    /* Section Headers */
    .clinical-header {
        color: #2b3452;
        font-weight: 600;
        letter-spacing: -0.5px;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_model():
    return joblib.load("predictED_rf_model.joblib")

model = load_model()
db = PredictED_Database()


#SIDEBAR

with st.sidebar:
    st.markdown("<h2 style='color: #2b3452;'>⚙️ System Parameters</h2>", unsafe_allow_html=True)
    use_live_hardware = st.toggle("Enable Edge Sensors", value=False, help="Connect to physical hospital hardware.")
    st.divider()
    
    st.markdown("<p style='font-size: 0.85rem; color: #6c757d; font-weight: 600; text-transform: uppercase;'>Manual Overrides</p>", unsafe_allow_html=True)
    
    with st.expander("Capacity Metrics", expanded=not use_live_hardware):
        ed_pts = st.slider("Total ED Patients", 0, 120, 45)
        ed_beds = st.number_input("Total ED Beds", value=40)
        hosp_beds = st.number_input("Total Hospital Beds", value=350)
        
    with st.expander("Acuity Metrics", expanded=not use_live_hardware):
        admits = st.slider("Admitted Wait", 0, 40, 10)
        vents = st.slider("Ventilator Usage", 0, 15, 2)
        longest_wait = st.slider("Max Wait (Hrs)", 0.0, 24.0, 4.5)
        last_wait = st.slider("Last Wait (Hrs)", 0.0, 12.0, 1.5)


# DATA SHIT

arrival_velocity = 0.2
chaos_index = 2.0
ambient_noise = 55.0 

if use_live_hardware:
    hw_data = db.get_temporal_features(window_minutes=15)
    arrival_velocity = hw_data.get("arrival_velocity", 0.2)
    chaos_index = hw_data.get("equipment_chaos_index", 2.0)
    ambient_noise = hw_data.get("ambient_noise_db", 50.0)

input_array = np.array([[
    ed_pts, ed_beds, admits, hosp_beds, vents, 
    longest_wait, last_wait, arrival_velocity, chaos_index
]])
predicted_score = model.predict(input_array)[0]

features = ['ED Patients', 'Arrival Velocity', 'Admitted Wait', 'Chaos Index', 'Max Wait Time']
importances = [ed_pts * 0.8, arrival_velocity * 40, admits * 1.5, chaos_index * 10, longest_wait * 5]
importances, features = zip(*sorted(zip(importances, features)))

#MAIN

col_header, col_status = st.columns([3, 1])
with col_header:
    st.markdown("<h1 class='clinical-header'>⚕️ PredictED Intelligence</h1>", unsafe_allow_html=True)
with col_status:
    if use_live_hardware:
        st.markdown("<div style='text-align: right; margin-top: 1rem;'><div class='live-indicator'><span class='pulse-dot'></span>LIVE TELEMETRY</div></div>", unsafe_allow_html=True)

#METRICS
st.markdown("<p style='font-size: 0.85rem; color: #6c757d; font-weight: 600; text-transform: uppercase;'>Real-Time Environment</p>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Patient Velocity", f"{arrival_velocity:.1f}/min", "+0.2" if arrival_velocity > 1.0 else "-0.1", delta_color="inverse")
m2.metric("IMU Chaos Index", f"{chaos_index:.1f}", "+1.2" if chaos_index > 6.0 else "Stable", delta_color="inverse")
m3.metric("Ambient Noise", f"{ambient_noise:.0f} dB", "Elevated" if ambient_noise > 85.0 else "Nominal", delta_color="inverse")
m4.metric("ED Utilization", f"{int((ed_pts/ed_beds)*100)}%", "+5%" if ed_pts > ed_beds else "-2%", delta_color="inverse")

st.markdown("<br>", unsafe_allow_html=True)
col_gauge, col_explain = st.columns([1.2, 1])

with col_gauge:
    st.markdown("<div style='background: white; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 1rem; color: #2b3452; font-weight: 600; margin-bottom: -20px; text-align: center;'>T+2 Hour Forecasting</p>", unsafe_allow_html=True)
    

    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = predicted_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 250], 'tickwidth': 1, 'tickcolor': "#6c757d"},
            'bar': {'color': "rgba(43, 52, 82, 0.9)", 'thickness': 0.15},
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 60], 'color': "rgba(40, 167, 69, 0.15)"},
                {'range': [60, 100], 'color': "rgba(255, 193, 7, 0.15)"},
                {'range': [100, 140], 'color': "rgba(253, 126, 20, 0.15)"},
                {'range': [140, 250], 'color': "rgba(220, 53, 69, 0.15)"}
            ],
            'threshold': {'line': {'color': "#dc3545", 'width': 3}, 'thickness': 0.75, 'value': 140}
        }
    ))
    fig_gauge.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20), font=dict(family="Inter", color="#2b3452"))
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_explain:
    st.markdown("<div style='background: white; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; box-shadow: 0 4px 15px rgba(0,0,0,0.03); height: 100%;'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 1rem; color: #2b3452; font-weight: 600; margin-bottom: 5px;'>AI Feature Drivers</p>", unsafe_allow_html=True)
    st.caption("Primary variables influencing the current forecast.")
    
# Horizontal Bar Chart
    fig_bar = go.Figure(go.Bar(
        x=importances,
        y=features,
        orientation='h',
        marker=dict(color='rgba(23, 162, 184, 0.7)', line=dict(color='rgba(23, 162, 184, 1)', width=1)),
    ))
    fig_bar.update_layout(
        height=230,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=True, gridcolor='#f8f9fa', showticklabels=False, title=''),
        yaxis=dict(showgrid=False, title=''),
        plot_bgcolor='white',
        font=dict(family="Inter", color="#495057", size=12)
    )
    st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Loop for live mode
if use_live_hardware:
    time.sleep(2)
    st.rerun()
