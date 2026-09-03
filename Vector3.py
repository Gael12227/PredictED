import pyaudio
import numpy as np
import requests
import time

SERVER_URL = "http://172.20.10.9:5000/api/sensor-data" 

# Audio configurations
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

p = pyaudio.PyAudio()

stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

print("🎙️ Raspberry Pi USB Mic Listening for Waiting Room Chaos...")

last_send_time = 0

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        
        # Calculate Root Mean Square (RMS) volume level
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        
        # Convert RMS to an estimated dB scale (40dB room baseline to ~100dB loud)
        db = 20 * np.log10(rms + 1e-5) + 30
        db = max(40.0, min(110.0, db))

        # Send telemetry every 1.5 seconds if room noise exceeds 75 dB (clapping/shouting)
        if db > 75.0 and (time.time() - last_send_time > 1.5):
            payload = {
                "device_id": "rpi_mic_array",
                "patient_delta": 0,
                "ambient_noise_db": round(float(db), 1)
            }
            try:
                res = requests.post(SERVER_URL, json=payload, timeout=1)
                print(f"[CHAOS DETECTED] Noise: {round(db, 1)} dB | Response: {res.status_code}")
            except Exception as e:
                print(f"Server unreachable: {e}")
            
            last_send_time = time.time()
            
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping Audio Listener...")
    stream.stop_stream()
    stream.close()
    p.terminate()
