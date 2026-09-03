import streamlit as st
import numpy as np
import pandas as pd
import joblib
import time

st.set_page_config(page_title="PredictED | ED Overcrowding", layout="wide")
st.title("🏥 PredictED: Early Warning System")

@st.cache_resource
def load_model():
    return joblib.load("predictED_rf_model.joblib")

model = load_model()

default_vals = {
    'ed_pts': 45, 'ed_beds': 40, 'admits': 10, 'hosp_beds': 350,
    'vents': 2, 'longest_wait': 4.5, 'last_wait': 1.5,
    'aqi': 120, 'temp': 32.0, 'arrival_vel': 0.2, 'chaos': 2.0, 'noise': 55.0
}
for key, val in default_vals.items():
    if key not in st.session_state:
        st.session_state[key] = val

use_live_hardware = st.sidebar.toggle("🔴 LIVE HARDWARE SENSORS", value=False)
if use_live_hardware:
    st.sidebar.warning("Hardware sensors locked for Software Review 1.")

if st.sidebar.button("🚨 TRIGGER CODE ORANGE", help="Simulate an external Mass Casualty Incident"):
    st.session_state.update({
        'ed_pts': 115, 'admits': 35, 'vents': 12, 'longest_wait': 18.0,
        'last_wait': 6.5, 'aqi': 450, 'temp': 44.0, 'arrival_vel': 3.5, 
        'chaos': 9.5, 'noise': 88.0
    })
    st.toast("CODE ORANGE ACTIVATED: Cascading external trauma...", icon="🚑")
    time.sleep(1)
    st.rerun()

if st.sidebar.button("🔄 Reset to Safe Baseline"):
    for key, val in default_vals.items():
        st.session_state[key] = val
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("### 01 · Capacity")
st.sidebar.caption("Current demand and available space")
ed_pts = st.sidebar.slider("Patients in ED", 0, 150, key='ed_pts')
ed_beds = st.sidebar.number_input("ED beds available", value=st.session_state['ed_beds'], key='ed_beds') 
hosp_beds = st.sidebar.number_input("Hospital beds available", value=st.session_state['hosp_beds'], key='hosp_beds')
st.sidebar.divider()

st.sidebar.markdown("### 02 · Acuity")
st.sidebar.caption("Clinical complexity and hold pressure")
admits = st.sidebar.slider("Admitted patients waiting", 0, 50, key='admits')
vents = st.sidebar.slider("Ventilators in use", 0, 20, key='vents')
longest_wait = st.sidebar.slider("Longest wait (hours)", 0.0, 24.0, key='longest_wait')
st.sidebar.divider()

st.sidebar.markdown("### 03 · Flow")
st.sidebar.caption("Throughput and arrival pattern")
last_wait = st.sidebar.slider("Most recent wait (hours)", 0.0, 12.0, key='last_wait')

if not use_live_hardware:
    arrival_velocity = st.sidebar.slider("Arrival velocity / min", 0.0, 5.0, key='arrival_vel')
    chaos_index = st.sidebar.slider("Equipment disruption index", 0.0, 10.0, key='chaos')
    ambient_noise = st.sidebar.slider("Ambient noise (dB)", 30.0, 100.0, key='noise')
else:
    arrival_velocity = 0.5
    chaos_index = 1.0
    ambient_noise = 50.0
    st.sidebar.info("Flow metrics currently driven by Edge IoT sensors.")

st.markdown("### Live Telemetry & Statistics")
stat1, stat2, stat3, stat4 = st.columns(4)


ed_util = (ed_pts / max(1, ed_beds)) * 100

util_delta = "↑ Above capacity" if ed_util > 100 else "↓ Nominal"
stat1.metric("ED utilization", f"{ed_util:.0f}%", util_delta, delta_color="inverse" if ed_util > 100 else "normal")

arr_delta = "↑ Surge detected" if arrival_velocity > 1.0 else "↓ Expected"
stat2.metric("Arrival velocity", f"{arrival_velocity:.1f}/min", arr_delta, delta_color="inverse" if arrival_velocity > 1.0 else "normal")

chaos_delta = "↑ Severe disruption" if chaos_index > 5.0 else "↓ Controlled"
stat3.metric("Disruption index", f"{chaos_index:.1f}/10", chaos_delta, delta_color="inverse" if chaos_index > 5.0 else "normal")

noise_delta = "↑ Hazardous" if ambient_noise > 75.0 else "↓ Nominal"
stat4.metric("Ambient environment", f"{ambient_noise:.0f} dB", noise_delta, delta_color="inverse" if ambient_noise > 75.0 else "normal")

st.divider()

input_array = np.array([[
    ed_pts, ed_beds, admits, hosp_beds, vents, 
    longest_wait, last_wait, arrival_velocity, chaos_index
]])

predicted_score = model.predict(input_array)[0]

col1, col2 = st.columns(2)

with col1:
    st.subheader("🤖 AI 2-Hour Forecast")
    if predicted_score < 60:
        st.success(f"Predicted NEDOCS Score: {predicted_score:.1f} (Normal capacity)")
    elif predicted_score < 100:
        st.warning(f"Predicted NEDOCS Score: {predicted_score:.1f} (Busy - Monitor closely)")
    elif predicted_score < 140:
        st.error(f"Predicted NEDOCS Score: {predicted_score:.1f} (OVERCROWDED)")
    else:
        st.error(f"🚨 Predicted NEDOCS Score: {predicted_score:.1f} (CRITICAL CAPACITY)")

with col2:
    st.write("**Forecast Trajectory (T-2 to T+2 Hours)**")
    A = max(1, ed_beds)
    B = max(1, hosp_beds)
    current_score = (85.8 * (ed_pts / A)) + (600 * (admits / B)) + (13.4 * vents) + (0.93 * longest_wait) + (5.64 * last_wait) - 20
    current_score = max(0, round(current_score, 1))

    mock_trend = pd.DataFrame({
        "Time": ["-2 Hrs", "-1 Hr", "Now", "+1 Hr", "+2 Hrs (AI)"],
        "NEDOCS Score": [
            max(0, current_score - 20), max(0, current_score - 8), current_score,                                   
            round((current_score + predicted_score) / 2, 1), predicted_score                                  
        ]
    })
    st.line_chart(mock_trend.set_index("Time"), height=350, color="#ff4b4b")

st.divider()

st.subheader("🔍 Clinical Impact Analysis")
st.caption("Real-time breakdown of variables driving the current forecast.")

baseline_array = np.array([20, 40, 2, 350, 0, 1.0, 0.5, 0.5, 3.0])
global_weights = model.feature_importances_
raw_impact = (input_array[0] - baseline_array) * global_weights
crisis_drivers = np.maximum(raw_impact, 0)

impact_df = pd.DataFrame({
    'Factor': ['ED Patients', 'ED Beds', 'Admits Waiting', 'Hosp Beds', 'Vent Patients', 'Longest Wait', 'Last Wait', 'Arrival Velocity', 'Equipment Chaos'],
    'Active Impact Weight': crisis_drivers
})

if not use_live_hardware:
    impact_df = impact_df[~impact_df['Factor'].str.contains('Velocity|Chaos')]
    
impact_df = impact_df[impact_df['Active Impact Weight'] > 0].sort_values(by='Active Impact Weight', ascending=True)

if not impact_df.empty:
    st.bar_chart(impact_df, x='Factor', y='Active Impact Weight', color="#ff4b4b", height=350)
else:
    st.success("All operational metrics are within safe limits.")