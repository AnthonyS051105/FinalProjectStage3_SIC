"""
Mock Service for Testing MQTT Communication
Simulates the actual AI service responses
"""

from flask import Flask, request, jsonify
import numpy as np
import random

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Mock AI Service',
        'bp_model_loaded': True,
        'stress_model_loaded': True
    })

@app.route('/predict_bp', methods=['POST'])
def predict_bp():
    """Mock Blood Pressure Prediction"""
    try:
        data = request.get_json()
        ppg = data.get('ppg', [])
        
        if len(ppg) < 100:
            return jsonify({'error': 'PPG signal too short'}), 400
        
        # Simulate prediction
        classes = ['Hypotension', 'Normal', 'Elevated', 'Hypertension Stage 1', 'Hypertension Stage 2', 'Hypertensive Crisis']
        class_id = random.choice([0, 1, 1, 1, 2, 3])  # Bias towards Normal/Elevated
        prediction = classes[class_id]
        
        # Simulate probabilities
        probabilities = [random.random() * 0.1 for _ in range(6)]
        probabilities[class_id] = 0.7 + random.random() * 0.25
        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]
        
        confidence = max(probabilities)
        
        # Simulate heart rate from PPG
        mean_bpm = random.uniform(60, 100)
        
        response = {
            'prediction': prediction,
            'class_id': class_id,
            'confidence': confidence,
            'probabilities': probabilities,
            'heart_rate': {
                'mean_bpm': mean_bpm,
                'std_bpm': random.uniform(2, 5),
                'min_bpm': mean_bpm - random.uniform(5, 10),
                'max_bpm': mean_bpm + random.uniform(5, 10),
                'num_peaks': random.randint(10, 15)
            },
            'features_extracted': 17
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict_stress', methods=['POST'])
def predict_stress():
    """Mock Stress Prediction"""
    try:
        data = request.get_json()
        ppg = data.get('ppg', [])
        temperature = data.get('temperature', [])
        
        if len(ppg) < 64:
            return jsonify({'error': 'PPG signal too short'}), 400
        
        if len(temperature) < 4:
            return jsonify({'error': 'Temperature signal too short'}), 400
        
        # Simulate prediction
        classes = ['Baseline', 'Stress', 'Amusement']
        class_id = random.choice([0, 0, 1, 2])  # Bias towards Baseline
        prediction = classes[class_id]
        
        # Simulate probabilities
        probabilities = [random.random() * 0.2 for _ in range(3)]
        probabilities[class_id] = 0.7 + random.random() * 0.25
        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]
        
        confidence = max(probabilities)
        
        # Simulate heart rate
        mean_bpm = random.uniform(65, 95)
        
        response = {
            'prediction': prediction,
            'class_id': class_id,
            'confidence': confidence,
            'probabilities': probabilities,
            'heart_rate': {
                'mean_bpm': mean_bpm,
                'std_bpm': random.uniform(3, 6),
                'min_bpm': mean_bpm - random.uniform(5, 12),
                'max_bpm': mean_bpm + random.uniform(5, 12),
                'rmssd_ms': random.uniform(20, 50),
                'sdnn_ms': random.uniform(35, 60)
            },
            'features_extracted': 21
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("Mock AI Service Starting...")
    print("Endpoints:")
    print("  GET  /health        - Health check")
    print("  POST /predict_bp    - Blood Pressure prediction")
    print("  POST /predict_stress - Stress prediction")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
