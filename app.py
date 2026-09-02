import streamlit as st
st.set_page_config(page_title="PredictED | ED Overcrowding", layout="wide")
st.title("🏥 PredictED: Early Warning System")
st.markdown("Live predictions of Emergency Department capacity breaches.")
st.sidebar.header("Current ED Conditions")
st.sidebar.caption("Adjust sliders to simulate hospital load:")
total_ed_patients = st.sidebar.slider("Total ED Patients", 0, 120, 45)
total_ed_beds = st.sidebar.number_input("Total ED Beds", value=40)
admits_waiting = st.sidebar.slider("Admitted Patients Waiting for Beds", 0, 40, 20)
total_hospital_beds = st.sidebar.number_input("Total Hospital Beds", value=350)
vent_patients = st.sidebar.slider("Patients on Ventilators", 0, 15, 7)
longest_admit_wait = st.sidebar.slider("Longest Admit Wait (Hours)", 0.0, 24.0, 4.5)
last_patient_wait = st.sidebar.slider("Last Patient Wait Time (Hours)", 0.0, 12.0, 1.5)

#placeholder for future ML model integration
def calculate_current_nedocs():
    # Avoid div by zero
    A = max(1, total_ed_beds)
    B = max(1, total_hospital_beds)
    
    score = (85.8 * (total_ed_patients / A)) + \
            (600 * (admits_waiting / B)) + \
            (13.4 * vent_patients) + \
            (0.93 * longest_admit_wait) + \
            (5.64 * last_patient_wait) - 20
    return max(0, round(score, 1))

current_score = calculate_current_nedocs()

#Main dashboard layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Current NEDOCS Score")
    if current_score < 60:
        st.success(f"Score: {current_score} (Normal)")
    elif current_score < 100:
        st.warning(f"Score: {current_score} (Busy)")
    elif current_score < 140:
        st.error(f"Score: {current_score} (Overcrowded)")
    else:
        st.error(f"🚨 Score: {current_score} (CRITICAL DISASTER)")
        
with col2:
    st.subheader("🤖 AI 2-Hour Prediction")
    st.info("Awaiting Machine Learning Model integration (Hour 4)...")

st.divider()
st.subheader("Model Feature Importance")
st.text("[Bar chart will appear here once Random Forest model is connected]")