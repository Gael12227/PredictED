import streamlit as st
import numpy as np
import pandas as pd
import joblib
import time
from database import PredictED_Database

# Initialization
st.set_page_config(page_title="PredictED | ED Overcrowding", layout="wide")
st.title("🏥 PredictED: Early Warning System")
@st.cache_resource
def load_model():
    return joblib.load("predictED_rf_model.joblib")
model = load_model()
db = PredictED_Database()

st.sidebar.header("System Control")
use_live_hardware = st.sidebar.toggle("🔴 LIVE HARDWARE SENSORS", value=False)
st.sidebar.divider()

st.sidebar.header("Clinical Conditions")
ed_pts = st.sidebar.slider("Total ED Patients", 0, 120, 45)
ed_beds = st.sidebar.number_input("Total ED Beds", value=40)
admits = st.sidebar.slider("Admitted Patients Waiting", 0, 40, 10)
hosp_beds = st.sidebar.number_input("Total Hospital Beds", value=350)
vents = st.sidebar.slider("Patients on Ventilators", 0, 15, 2)
longest_wait = st.sidebar.slider("Longest Admit Wait (Hrs)", 0.0, 24.0, 4.5)
last_wait = st.sidebar.slider("Last Patient Wait (Hrs)", 0.0, 12.0, 1.5)

if use_live_hardware:
    st.toast("Fetching live telemetry from Edge Sensors...", icon="📡")
    sensor_data = db.get_temporal_features(window_minutes=15)
    
    arrival_velocity = sensor_data['arrival_velocity']
    chaos_index = sensor_data['equipment_chaos_index']
    noise_db = sensor_data['ambient_noise_db']
    
    st.sidebar.success("Sensors: ONLINE")
    st.sidebar.metric("Arrival Velocity (Pts/Min)", arrival_velocity)
    st.sidebar.metric("Equipment Chaos (0-10)", chaos_index)
else:
    #default when hardware is off
    arrival_velocity = 0.5
    chaos_index = 1.0
    noise_db = 55.0
    st.sidebar.info("Sensors: OFFLINE (Manual Mode)")

# AI PREDICTION LOGIC 
feature_names = [
    'ed_pts', 'ed_beds', 'admits', 'hosp_beds', 'vents', 
    'longest_wait', 'last_wait', 'arrival_velocity', 'equipment_chaos_index'
]
input_array = np.array([[
    ed_pts, ed_beds, admits, hosp_beds, vents, 
    longest_wait, last_wait, arrival_velocity, chaos_index
]])
predicted_score = model.predict(input_array)[0]


col1, col2 = st.columns(2)
with col1:
    st.subheader("Hardware Status")
    if use_live_hardware:
        st.info("Input mode: **Live Edge IoT Network**")
        if chaos_index > 6.0:
            st.error("⚠️ HIGH PHYSICAL CHAOS DETECTED")
    else:
        st.info("Input mode: **Manual Simulation**")
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
if use_live_hardware:
    time.sleep(5)
    st.rerun()


st.divider()
st.subheader("Crisis Drivers")
importances = model.feature_importances_
importance_df = pd.DataFrame({
    'Factor': ['Total ED Patients', 'Total ED Beds', 'Admits Waiting', 'Total Hosp Beds', 'Vent Patients', 'Longest Wait', 'Last Patient Wait', 'Arrival Velocity (Hardware)', 'Equipment Chaos (Hardware)'],
    'Impact Weight': importances
}).sort_values(by='Impact Weight', ascending=True)
st.bar_chart(importance_df, x='Factor', y='Impact Weight', color="#ff4b4b", height=300)