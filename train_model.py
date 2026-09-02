import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib

print("Loading dataset...")
df = pd.read_csv("master_hospital_data.csv") 

features = [
    'ed_pts', 
    'ed_beds', 
    'admits', 
    'hosp_beds', 
    'vents', 
    'longest_wait', 
    'last_wait'
]
print("Shifting temporal target variable (T+2 hrs)...")
df['target_nedocs_2hr'] = df['nedocs_score'].shift(-2)
df = df.dropna(subset=['target_nedocs_2hr'])
X = df[features]
y = df['target_nedocs_2hr']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Training Random Forest Regressor...")
rf_model = RandomForestRegressor(
    n_estimators=100, 
    max_depth=10,
    random_state=42, 
    n_jobs=-1
)

rf_model.fit(X_train, y_train)

predictions = rf_model.predict(X_test)
r2 = r2_score(y_test, predictions)
mse = mean_squared_error(y_test, predictions)

print(f"\n--- Model Evaluation ---")
print(f"R2 Score: {r2:.3f} (Closer to 1.0 is better)")
print(f"Mean Squared Error: {mse:.2f}")


print("\n--- Feature Importances ---")
importances = dict(zip(features, rf_model.feature_importances_))
for feature, weight in sorted(importances.items(), key=lambda x: x[1], reverse=True):
    print(f"{feature}: {weight*100:.1f}%")

#to load into Streamlit
model_filename = "predictED_rf_model.joblib"
joblib.dump(rf_model, model_filename)
print(f"\nSuccess! Model exported to {model_filename}. Hand off to UI.")