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
    'vents': 2, 'longest_wait': 4.5, 'last_wait': 1.5
}
for key, val in default_vals.items():
    if key not in st.session_state:
        st.session_state[key] = val

st.sidebar.header("System Control")
use_live_hardware = st.sidebar.toggle("🔴 LIVE HARDWARE SENSORS", value=False)
if use_live_hardware:
    st.sidebar.warning("Hardware sensors locked for Software Review 1.")

st.sidebar.divider()

st.sidebar.header("Emergency Simulations")
if st.sidebar.button("🚨 TRIGGER CODE ORANGE", help="Simulate an external Mass Casualty Incident"):
    st.session_state['ed_pts'] = 115
    st.session_state['admits'] = 35
    st.session_state['vents'] = 12
    st.session_state['longest_wait'] = 18.0
    st.session_state['last_wait'] = 6.5
    st.toast("CODE ORANGE ACTIVATED: Inbound multi-vehicle trauma...", icon="🚑")
    time.sleep(1) 
    st.rerun()

if st.sidebar.button("🔄 Reset to Safe Baseline"):
    for key, val in default_vals.items():
        st.session_state[key] = val
    st.rerun()

st.sidebar.divider()

st.sidebar.header("Clinical Conditions")
ed_pts = st.sidebar.slider("Total ED Patients", 0, 150, key='ed_pts')
ed_beds = st.sidebar.number_input("Total ED Beds", value=40) 
admits = st.sidebar.slider("Admitted Patients Waiting", 0, 50, key='admits')
hosp_beds = st.sidebar.number_input("Total Hospital Beds", value=350)
vents = st.sidebar.slider("Patients on Ventilators", 0, 20, key='vents')
longest_wait = st.sidebar.slider("Longest Admit Wait (Hrs)", 0.0, 24.0, key='longest_wait')
last_wait = st.sidebar.slider("Last Patient Wait (Hrs)", 0.0, 12.0, key='last_wait')

arrival_velocity = 0.5
chaos_index = 1.0

input_array = np.array([[
    ed_pts, ed_beds, admits, hosp_beds, vents, 
    longest_wait, last_wait, arrival_velocity, chaos_index
]])

predicted_score = model.predict(input_array)[0]

col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Status")
    st.info("Input mode: **Software Simulation**")

    ratio = ed_pts / max(1, ed_beds)
    st.metric(
        label="Patient-to-Bed Ratio", 
        value=f"{ratio:.2f}x",
        delta=f"{(ratio - 1.0):.2f} over capacity" if ratio > 1 else "Normal",
        delta_color="inverse"
    )

with col2:
    st.subheader("🤖 AI 2-Hour Forecast")
    if predicted_score < 60:
        st.success(f"Predicted Score: {predicted_score:.1f} (Normal capacity)")
    elif predicted_score < 100:
        st.warning(f"Predicted Score: {predicted_score:.1f} (Busy - Monitor closely)")
    elif predicted_score < 140:
        st.error(f"Predicted Score: {predicted_score:.1f} (OVERCROWDED)")
    else:
        st.error(f"🚨 Predicted Score: {predicted_score:.1f} (CRITICAL CAPACITY)")


st.divider()
st.subheader("🔍 Clinical Impact Analysis")
st.caption("Real-time breakdown of the variables driving the current forecast.")

colA, colB = st.columns([2, 1])

with colA:
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
        st.bar_chart(impact_df, x='Factor', y='Active Impact Weight', color="#ff4b4b", height=250)
    else:
        st.success("All operational metrics are within safe limits.")

with colB:
    # 2. Clinical Threshold Translation & Alerts
    st.write("**Operational Alerts:**")
    
    if ratio >= 1.0:
        st.error(f"🚨 **Capacity Breach:** The ED is physically out of space.")
    elif ratio >= 0.8:
        st.warning(f"⚠️ **High Strain:** ED bed occupancy is approaching maximum.")
        
    if admits > 5:
         st.error(f"🚨 **Admit Bottleneck:** {admits} patients are boarding in the ED waiting for upstairs beds.")
         
    if vents > 5:
        st.error(f"🚨 **Critical Acuity:** High ventilator usage indicates severe respiratory trauma load.")

# Simulated Trajectory
st.write("**Forecast Trajectory (T-2 to T+2 Hours)**")
mock_trend = pd.DataFrame({
    "Time": ["-2 Hrs", "-1 Hr", "Now", "+1 Hr (Predicted)", "+2 Hrs (Predicted)"],
    "NEDOCS Score": [
        max(0, predicted_score - 25), 
        max(0, predicted_score - 10), 
        predicted_score, 
        predicted_score + 15, 
        predicted_score + 22
    ]
})
st.line_chart(mock_trend.set_index("Time"), height=150, color="#ff4b4b")