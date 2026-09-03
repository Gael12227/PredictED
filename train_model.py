import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib

def upgrade_and_train():
    print("Loading Real Delhi Datasets...")
    
    rural_df = pd.read_csv("delhi_Rural.csv")
    urban_df = pd.read_csv("Delhi_urban.csv")

    rural_map = {
        'Total_Patients_in_ED': 'ed_pts',
        'ED_Total_Beds': 'ed_beds',
        'Patients_Waiting_for_Admit_Bed': 'admits',
        'Hospital_Total_Beds': 'hosp_beds',
        'ED_Respirators_in_Use': 'vents',
        'Longest_Admit_Wait_Time_Minutes': 'longest_wait',
        'Average_Wait_Time_Mins': 'last_wait',
        'NEDOCS_Total_Score': 'current_nedocs_score'
    }
    rural_clean = rural_df[list(rural_map.keys())].rename(columns=rural_map)

    urban_map = {
        'NEDOCS_Param_3_ED_Patients_Count': 'ed_pts',
        'NEDOCS_Param_1_ED_Total_Beds': 'ed_beds',
        'NEDOCS_Param_4_Patients_Waiting_Admit': 'admits',
        'NEDOCS_Param_2_Hospital_Total_Beds': 'hosp_beds',
        'NEDOCS_Param_7_ED_Respirators_In_Use': 'vents',
        'NEDOCS_Param_5_Longest_Wait_Minutes': 'longest_wait',
        'Average_Wait_Time_Mins': 'last_wait',
        'NEDOCS_Total_Score': 'current_nedocs_score'
    }
    urban_clean = urban_df[list(urban_map.keys())].rename(columns=urban_map)
    df = pd.concat([rural_clean, urban_clean], ignore_index=True)
    df['longest_wait'] = (df['longest_wait'] / 60.0).round(2)
    df['last_wait'] = (df['last_wait'] / 60.0).round(2)
    print("Synthesizing Edge Hardware Features...")
    df['ambient_noise_db'] = np.clip(50 + (df['ed_pts'] * 0.4) + (df['vents'] * 2.5) + np.random.normal(0, 5, len(df)), 40, 95).round(1)
    df['arrival_velocity'] = np.where(
        np.random.rand(len(df)) > 0.90, 
        np.random.uniform(1.0, 3.0, len(df)), 
        np.random.uniform(0.1, 0.5, len(df))
    ).round(2)
    df['equipment_chaos_index'] = np.where(
        np.random.rand(len(df)) > 0.90, 
        np.random.uniform(7.0, 10.0, len(df)), 
        np.random.uniform(0.0, 3.0, len(df))
    ).round(1)
    df['target'] = df['current_nedocs_score'].shift(-2)
    df['target'] += (df['equipment_chaos_index'] * 3.5)
    df['target'] += (df['arrival_velocity'] * 15.0)
    df['target'] = np.clip(df['target'], 0, 250).round(1)
    df.dropna(subset=['target'], inplace=True)

    print("Training Random Forest Regressor on unified Delhi data...")
    features = ['ed_pts', 'ed_beds', 'admits', 'hosp_beds', 'vents', 'longest_wait', 'last_wait', 'arrival_velocity', 'equipment_chaos_index']
    
    X = df[features]
    y = df['target']
    
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(X, y)

    importances = dict(zip(features, rf.feature_importances_))
    print("\n--- FEATURE IMPORTANCES ---")
    for k, v in sorted(importances.items(), key=lambda x: x[1], reverse=True):
        print(f"{k}: {v*100:.1f}%")

    joblib.dump(rf, "predictED_rf_model.joblib")
    print("\n Success! New model saved as 'predictED_rf_model.joblib'.")

if __name__ == "__main__":
    upgrade_and_train()