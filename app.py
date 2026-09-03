import streamlit as st
import numpy as np
import pandas as pd
import joblib
import time

# ---------------------------------------------------------
# PAGE SETUP & INITIALIZATION
# ---------------------------------------------------------
st.set_page_config(page_title="PredictED | ED Overcrowding", layout="wide")
st.title("🏥 PredictED: Early Warning System")

@st.cache_resource
def load_model():
    # Make sure your model file is in the same directory!
    return joblib.load("predictED_rf_model.joblib")

model = load_model()

# Initialize Session State for sliders so the button can overwrite them
default_vals = {
    'ed_pts': 45, 'ed_beds': 40, 'admits': 10, 'hosp_beds': 350,
    'vents': 2, 'longest_wait': 4.5, 'last_wait': 1.5,
    'aqi': 120, 'temp': 32.0 
}
for key, val in default_vals.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------
# SIDEBAR: SYSTEM CONTROL & SIMULATION
# ---------------------------------------------------------
st.sidebar.header("System Control")
use_live_hardware = st.sidebar.toggle("🔴 LIVE HARDWARE SENSORS", value=False)
if use_live_hardware:
    st.sidebar.warning("Hardware sensors locked for Software Review 1.")

st.sidebar.divider()

# THE CRISIS BUTTON
st.sidebar.header("Emergency Simulations")
if st.sidebar.button("🚨 TRIGGER CODE ORANGE", help="Simulate an external Mass Casualty Incident"):
    # Instantly override session state to catastrophic levels
    st.session_state['ed_pts'] = 115
    st.session_state['admits'] = 35
    st.session_state['vents'] = 12
    st.session_state['longest_wait'] = 18.0
    st.session_state['last_wait'] = 6.5
    st.session_state['aqi'] = 450     # Toxic Air
    st.session_state['temp'] = 44.0   # Heatwave
    st.toast("CODE ORANGE ACTIVATED: Cascading external trauma...", icon="🚑")
    time.sleep(1) # Pause to let the toast render
    st.rerun()

if st.sidebar.button("🔄 Reset to Safe Baseline"):
    for key, val in default_vals.items():
        st.session_state[key] = val
    st.rerun()

st.sidebar.divider()

# ---------------------------------------------------------
# SIDEBAR: DEMOGRAPHICS & ENVIRONMENT
# ---------------------------------------------------------
st.sidebar.header("Environment & Demographics")
region = st.sidebar.radio("Hospital Location", ["Urban (Delhi)", "Rural (Outskirts)"])

if region == "Urban (Delhi)":
    season = st.sidebar.selectbox("Season", ["Off-Peak", "Peak Tourist (Oct-Mar)"])
else:
    season = st.sidebar.selectbox("Season", ["Off-Season / Sowing", "Active Harvest"])
    
aqi = st.sidebar.slider("Air Quality Index (AQI)", 0, 500, key='aqi')
temp = st.sidebar.slider("Temperature (°C)", 10.0, 50.0, key='temp')

st.sidebar.divider()

# ---------------------------------------------------------
# SIDEBAR: CLINICAL METRIC SLIDERS
# ---------------------------------------------------------
st.sidebar.header("Clinical Conditions")
ed_pts = st.sidebar.slider("Total ED Patients", 0, 150, key='ed_pts')
ed_beds = st.sidebar.number_input("Total ED Beds", value=st.session_state['ed_beds'], key='ed_beds') 
admits = st.sidebar.slider("Admitted Patients Waiting", 0, 50, key='admits')
hosp_beds = st.sidebar.number_input("Total Hospital Beds", value=st.session_state['hosp_beds'], key='hosp_beds')
vents = st.sidebar.slider("Patients on Ventilators", 0, 20, key='vents')
longest_wait = st.sidebar.slider("Longest Admit Wait (Hrs)", 0.0, 24.0, key='longest_wait')
last_wait = st.sidebar.slider("Last Patient Wait (Hrs)", 0.0, 12.0, key='last_wait')

# Static hardware variables for Review 1
arrival_velocity = 0.5
chaos_index = 1.0

# ---------------------------------------------------------
# AI PREDICTION LOGIC 
# ---------------------------------------------------------
# Order must match the trained model features perfectly
input_array = np.array([[
    ed_pts, ed_beds, admits, hosp_beds, vents, 
    longest_wait, last_wait, arrival_velocity, chaos_index
]])

predicted_score = model.predict(input_array)[0]

# ---------------------------------------------------------
# MAIN DASHBOARD PANELS
# ---------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Status")
    st.info("Input mode: **Software Simulation**")
    
    # Live Patient-to-Bed Ratio Metric
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

# ---------------------------------------------------------
# EXPLAINABILITY 2.0: CLINICAL DRIVERS & TRAJECTORY
# ---------------------------------------------------------
st.divider()
st.subheader("🔍 Clinical Impact Analysis")
st.caption("Real-time breakdown of the variables driving the current forecast.")

colA, colB = st.columns([2, 1])

with colA:
    # 1. Local Feature Impact
    baseline_array = np.array([20, 40, 2, 350, 0, 1.0, 0.5, 0.5, 3.0])
    global_weights = model.feature_importances_
    raw_impact = (input_array[0] - baseline_array) * global_weights
    crisis_drivers = np.maximum(raw_impact, 0)
    
    impact_df = pd.DataFrame({
        'Factor': ['ED Patients', 'ED Beds', 'Admits Waiting', 'Hosp Beds', 'Vent Patients', 'Longest Wait', 'Last Wait', 'Arrival Velocity', 'Equipment Chaos'],
        'Active Impact Weight': crisis_drivers
    })
    
    # Hide the hardware features for Review 1
    if not use_live_hardware:
        impact_df = impact_df[~impact_df['Factor'].str.contains('Velocity|Chaos')]
        
    impact_df = impact_df[impact_df['Active Impact Weight'] > 0].sort_values(by='Active Impact Weight', ascending=True)
    
    if not impact_df.empty:
        st.bar_chart(impact_df, x='Factor', y='Active Impact Weight', color="#ff4b4b", height=300)
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

    # --- Contextual Demographic & Environmental Alerts ---
    st.write("**Contextual Risk Factors:**")
    
    if aqi >= 300:
        st.warning(f"🌫️ **Hazardous Air Quality (AQI {aqi}):** Anticipate a secondary surge in COPD, asthma exacerbations, and pediatric respiratory distress.")
    elif aqi >= 200:
        st.info(f"💨 **Poor Air Quality (AQI {aqi}):** Monitor for increased respiratory chief complaints.")
        
    if temp >= 42.0:
        st.warning(f"🌡️ **Extreme Heatwave ({temp}°C):** Elevated risk for geriatric heatstroke and severe dehydration admissions.")
        
    if region == "Rural (Outskirts)" and season == "Active Harvest":
        st.warning("🌾 **Agricultural Demographic:** Historical dataset indicates a 20% increased risk of agricultural trauma and toxicology (animal/snake bites) during harvest.")
    elif region == "Urban (Delhi)" and season == "Peak Tourist (Oct-Mar)":
        st.info("✈️ **Tourist Demographic:** Expect higher volume of non-local leisure/medical tourists requiring translation or specialized coordination.")

# 3. Simulated Trajectory (Temporal Context)
st.write("**Forecast Trajectory (T-2 to T+2 Hours)**")

# Calculate the ACTUAL current score using the raw clinical formula
A = max(1, ed_beds)
B = max(1, hosp_beds)
current_score = (85.8 * (ed_pts / A)) + (600 * (admits / B)) + (13.4 * vents) + (0.93 * longest_wait) + (5.64 * last_wait) - 20
current_score = max(0, round(current_score, 1))

# Build the trajectory logically
mock_trend = pd.DataFrame({
    "Time": ["-2 Hrs", "-1 Hr", "Now", "+1 Hr", "+2 Hrs (AI Forecast)"],
    "NEDOCS Score": [
        max(0, current_score - 20), 
        max(0, current_score - 8), 
        current_score,                                   
        round((current_score + predicted_score) / 2, 1), 
        predicted_score                                  
    ]
})

st.line_chart(mock_trend.set_index("Time"), height=350, color="#ff4b4b")