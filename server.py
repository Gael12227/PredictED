from flask import Flask, request, jsonify
from database import PredictED_Database

app = Flask(__name__)
db = PredictED_Database()

@app.route('/api/sensors', methods=['POST'])
def receive_sensor_data():
    """
    Catches HTTP POST requests from the edge hardware.
    Expected JSON payload: {"sensor_type": "string", "value": float}
    """
    try:
        incoming_data = request.json
        sensor_type = incoming_data.get('sensor_type')
        value = incoming_data.get('value')
        # Log to terminal for demo
        print(f"📡 Edge Telemetry Received: [ {sensor_type} ] = {value}")
        db.insert_reading(sensor_type, value)
            
        return jsonify({"status": "success", "message": "Telemetry logged"}), 200
        
    except Exception as e:
        print(f"❌ Error processing payload: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    print("🚀 PredictED Hardware API initializing...")
    print("⚠️  REMINDER: Ensure your ESP32/NodeMCU C++ code points to THIS computer's IPv4 address!")
    app.run(host='0.0.0.0', port=5000, debug=True)