import pandas as pd
import numpy as np

def upgrade_training_data():
    print("Loading original dataset...")
    df = pd.read_csv("upgraded_temporal_data.csv")
    
    print("Synthesizing independent temporal and hardware features...")
    noise_base = 50 + (df['ed_pts'] * 0.4) + (df['vents'] * 2.5) + np.random.normal(0, 5, len(df))
    df['ambient_noise_db'] = np.clip(noise_base, 40, 95).round(1)
    
    # 2. Arrival Velocity: Realistic Scales
    # Normal: 0.1 to 0.5 pts/min. Crisis (Bus Crash): 1.0 to 3.0 pts/min.
    df['arrival_velocity'] = np.where(
        np.random.rand(len(df)) > 0.90, 
        np.random.uniform(1.0, 3.0, len(df)), 
        np.random.uniform(0.1, 0.5, len(df))
    ).round(2)
    
    # 3. Equipment Chaos: 0-3 (Walking), 7-10 (Frantic Gurney Movement)
    df['equipment_chaos_index'] = np.where(
        np.random.rand(len(df)) > 0.90, 
        np.random.uniform(7.0, 10.0, len(df)), 
        np.random.uniform(0.0, 3.0, len(df))
    ).round(1)
    
    # 4. The Time-Shift Fix: Create the future target BEFORE penalizing
    # We want to predict the clinical score 2 hours from now
    if 'nedocs_score' not in df.columns:
        # Assuming the master file uses 'current_nedocs_score' based on previous context
        score_col = 'nedocs_score' if 'nedocs_score' in df.columns else 'nedocs_score'
    else:
        score_col = 'nedocs_score'
        
    df['target'] = df[score_col].shift(-2)
    
    # 5. Apply the Predictive Hardware Penalty
    # If chaos or velocity is high NOW, the FUTURE clinical score will realistically surge.
    df['target'] += (df['equipment_chaos_index'] * 3.5)  # Adds up to ~35 points to the future target
    df['target'] += (df['arrival_velocity'] * 15.0)      # Adds up to ~45 points to the future target
    
    # Cap the future target at a realistic clinical maximum (250 is catastrophic)
    df['target'] = np.clip(df['target'], 0, 250).round(1)
    
    # Drop the empty rows at the bottom caused by the shift
    df.dropna(subset=['target'], inplace=True)
    
    # Save the upgraded dataset
    output_filename = "upgraded_temporal_data.csv"
    df.to_csv(output_filename, index=False)
    
    print(f"Success! Upgraded dataset saved to {output_filename}.")
    print("New Features Added: 'arrival_velocity', 'equipment_chaos_index', 'ambient_noise_db'")

if __name__ == "__main__":
    upgrade_training_data()