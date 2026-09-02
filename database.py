import sqlite3
from datetime import datetime, timedelta

class PredictED_Database:
    def __init__(self, db_name="predictED_live.db"):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self):
        # check_same_thread=False allows Flask to query the DB asynchronously
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def _init_db(self):
        """Creates the schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hardware_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sensor_type TEXT,
                    value REAL
                )
            ''')
            conn.commit()

    def insert_reading(self, sensor_type, value):
        """Logs a raw ping from the ESP32, NodeMCU, or Raspberry Pi."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO hardware_logs (sensor_type, value) VALUES (?, ?)", 
                (sensor_type, float(value))
            )
            conn.commit()

    def get_temporal_features(self, window_minutes=15):
        """
        The synthesis engine: Pulls the rolling metrics for the ML model.
        Calculates how fast the ED is filling up and the environmental chaos.
        """
        time_threshold = datetime.utcnow() - timedelta(minutes=window_minutes)
        time_str = time_threshold.strftime('%Y-%m-%d %H:%M:%S')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Arrival Velocity (Count of ultrasound triggers in the last 15 mins)
            cursor.execute('''
                SELECT COUNT(*) FROM hardware_logs 
                WHERE sensor_type = 'ultrasound_inflow' AND timestamp >= ?
            ''', (time_str,))
            arrival_velocity = cursor.fetchone()[0]

            # 2. Equipment Chaos Index (Average IMU Z-axis variance)
            cursor.execute('''
                SELECT AVG(value) FROM hardware_logs 
                WHERE sensor_type = 'imu_variance' AND timestamp >= ?
            ''', (time_str,))
            chaos_index_result = cursor.fetchone()[0]
            equipment_chaos = chaos_index_result if chaos_index_result else 0.0

            # 3. Ambient Noise Level (Average dB from the USB Mic)
            cursor.execute('''
                SELECT AVG(value) FROM hardware_logs 
                WHERE sensor_type = 'mic_decibels' AND timestamp >= ?
            ''', (time_str,))
            noise_result = cursor.fetchone()[0]
            ambient_noise = noise_result if noise_result else 50.0 # Default quiet room

        return {
            "arrival_velocity": arrival_velocity,
            "equipment_chaos_index": round(equipment_chaos, 2),
            "ambient_noise_db": round(ambient_noise, 1)
        }

# Initialize it once to be imported by your Flask server (server.py)
db = PredictED_Database()