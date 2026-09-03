import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def calculate_nedocs(ed_pts, ed_beds, admits, hosp_beds, vents, longest_wait, last_wait):
    """Calculates standard NEDOCS score."""
    if ed_beds == 0 or hosp_beds == 0:
        return 0.0
    score = (
        (85.8 * (ed_pts / ed_beds)) +
        (600.0 * (admits / hosp_beds)) +
        (13.4 * vents) +
        (0.93 * longest_wait) +
        (5.64 * last_wait) -
        20.0
    )
    return max(0.0, round(float(score), 2))

def generate_synthetic_dataset(rows=10000):
    np.random.seed(42)
    start_time = datetime(2026, 1, 1, 0, 0)
    data = []

    # Fixed capacity baseline
    total_ed_beds = 30
    total_hosp_beds = 350

    for i in range(rows):
        current_time = start_time + timedelta(hours=i)
        hour = current_time.hour
        day_of_week = current_time.weekday() # 0 = Mon, 6 = Sun

        # Time variance multipliers
        time_factor = 1.0
        if 17 <= hour <= 22:  # Evening spike
            time_factor += 0.4
        elif 1 <= hour <= 6:   # Night drop
            time_factor -= 0.3

        if day_of_week in [4, 5]: # Fri/Sat weekend surge
            time_factor += 0.25

        # Variable generation with realistic correlation
        base_pts = int(np.random.poisson(22) * time_factor)
        total_ed_pts = max(5, min(65, base_pts))
        
        admits_waiting = int(np.random.binomial(total_ed_pts, 0.25))
        vent_pts = int(np.random.binomial(total_ed_pts, 0.05))
        
        longest_admit_wait = round(max(0.5, (admits_waiting * 0.8) + np.random.uniform(0, 3)), 2)
        wait_time_last_pt = round(max(0.1, (total_ed_pts / total_ed_beds * 1.2) + np.random.uniform(0, 1.5)), 2)

        score = calculate_nedocs(
            total_ed_pts, total_ed_beds, admits_waiting, 
            total_hosp_beds, vent_pts, longest_admit_wait, wait_time_last_pt
        )

        data.append({
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_ed_patients": total_ed_pts,
            "total_ed_beds": total_ed_beds,
            "admits_waiting": admits_waiting,
            "total_hospital_beds": total_hosp_beds,
            "vent_patients": vent_pts,
            "longest_admit_wait_hrs": longest_admit_wait,
            "wait_time_last_pt_hrs": wait_time_last_pt,
            "nedocs_score": score
        })

    df = pd.DataFrame(data)
    df.to_csv("synthetic_nedocs_data.csv", index=False)
    print(f"Dataset generated successfully: {rows} rows -> synthetic_nedocs_data.csv")

if __name__ == "__main__":
    generate_synthetic_dataset(10000)


    
