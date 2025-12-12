import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- Dashboard UI Configuration ---
st.set_page_config(page_title="SIC Stage 3 - Health Monitor", layout="wide", page_icon="🏥")

# --- Custom CSS ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    .alert-danger {
        background-color: #f8d7da;
        color: #721c24;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #f5c6cb;
        margin: 10px 0;
    }
    .alert-warning {
        background-color: #fff3cd;
        color: #856404;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ffeeba;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_BP = "sic/stage3/bp_data"
MQTT_TOPIC_STRESS = "sic/stage3/stress_data"
SERVICE_URL = "http://localhost:7860"  # Service port

# --- Session State ---
if 'bp_history' not in st.session_state:
    st.session_state.bp_history = []

if 'stress_history' not in st.session_state:
    st.session_state.stress_history = []

if 'bp_result' not in st.session_state:
    st.session_state.bp_result = None

if 'stress_result' not in st.session_state:
    st.session_state.stress_result = None

if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

# --- Alert Tracking ---
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = {
        'hypertension_start': None,
        'hypotension_start': None,
        'stress_start': None
    }

# --- Global queues (persistent across reruns) ---
import queue

class SharedData:
    def __init__(self):
        self.bp_queue = queue.Queue()
        self.stress_queue = queue.Queue()

@st.cache_resource
def get_shared_data():
    return SharedData()

shared_data = get_shared_data()

# Helper function to pad/interpolate samples
def pad_samples(data, target_length):
    """Pad array to target length by repeating last value"""
    current_length = len(data)
    if current_length >= target_length:
        return data[:target_length]
    elif current_length == 0:
        return [0] * target_length
    else:
        # Repeat last value to fill
        padding = [data[-1]] * (target_length - current_length)
        return data + padding

# --- MQTT Callbacks ---
def on_message_bp(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        ppg_data = payload.get('ppg', [])
        
        print(f"BP data received: {len(ppg_data)} PPG samples")
        
        # Pad to 1000 if less
        if len(ppg_data) < 1000:
            print(f"Padding PPG from {len(ppg_data)} to 1000 samples")
            ppg_data = pad_samples(ppg_data, 1000)
        
        # Send to service
        response = requests.post(
            f"{SERVICE_URL}/predict_bp",
            json={"ppg": ppg_data},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            # Store in shared queue
            shared_data.bp_queue.put(result)
            print(f"BP prediction: {result.get('prediction')}")
        else:
            print(f"BP service error: {response.status_code}")
                
    except Exception as e:
        print(f"Error processing BP data: {e}")

def on_message_stress(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        ppg_data = payload.get('ppg', [])
        temp_data = payload.get('temperature', [])
        
        print(f"Stress data received: {len(ppg_data)} PPG, {len(temp_data)} Temp samples")
        
        # Pad to expected sizes
        if len(ppg_data) < 640:
            print(f"Padding PPG from {len(ppg_data)} to 640 samples")
            ppg_data = pad_samples(ppg_data, 640)
        if len(temp_data) < 40:
            print(f"Padding Temp from {len(temp_data)} to 40 samples")
            temp_data = pad_samples(temp_data, 40)
        
        # Send to service
        response = requests.post(
            f"{SERVICE_URL}/predict_stress",
            json={"ppg": ppg_data, "temperature": temp_data},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            # Store in shared queue
            shared_data.stress_queue.put(result)
            print(f"Stress prediction: {result.get('prediction')}")
        else:
            print(f"Stress service error: {response.status_code}")
                
    except Exception as e:
        print(f"Error processing Stress data: {e}")

@st.cache_resource
def start_mqtt():
    try:
        client_bp = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client_bp = mqtt.Client()
    
    client_bp.on_message = on_message_bp
    client_bp.connect(MQTT_BROKER, MQTT_PORT, 60)
    client_bp.subscribe(MQTT_TOPIC_BP)
    client_bp.loop_start()
    
    try:
        client_stress = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client_stress = mqtt.Client()
        
    client_stress.on_message = on_message_stress
    client_stress.connect(MQTT_BROKER, MQTT_PORT, 60)
    client_stress.subscribe(MQTT_TOPIC_STRESS)
    client_stress.loop_start()
    
    return client_bp, client_stress

# Start MQTT
client_bp, client_stress = start_mqtt()

# --- Alert System ---
def check_alerts():
    alerts = []
    now = datetime.now()
    
    # Check Blood Pressure
    if st.session_state.bp_result:
        bp_pred = st.session_state.bp_result.get('prediction', '')
        
        if 'Hypertension' in bp_pred:
            if st.session_state.alert_history['hypertension_start'] is None:
                st.session_state.alert_history['hypertension_start'] = now
            else:
                duration = (now - st.session_state.alert_history['hypertension_start']).total_seconds() / 60
                if duration > 5:  # Alert after 5 minutes
                    alerts.append({
                        'type': 'danger',
                        'message': f"⚠️ PERINGATAN: Hipertensi terdeteksi selama {duration:.1f} menit!"
                    })
        else:
            st.session_state.alert_history['hypertension_start'] = None
            
        if 'Hypotension' in bp_pred:
            if st.session_state.alert_history['hypotension_start'] is None:
                st.session_state.alert_history['hypotension_start'] = now
            else:
                duration = (now - st.session_state.alert_history['hypotension_start']).total_seconds() / 60
                if duration > 5:
                    alerts.append({
                        'type': 'danger',
                        'message': f"⚠️ PERINGATAN: Hipotensi terdeteksi selama {duration:.1f} menit!"
                    })
        else:
            st.session_state.alert_history['hypotension_start'] = None
    
    # Check Stress
    if st.session_state.stress_result:
        stress_pred = st.session_state.stress_result.get('prediction', '')
        
        if stress_pred == 'Stress':
            if st.session_state.alert_history['stress_start'] is None:
                st.session_state.alert_history['stress_start'] = now
            else:
                duration = (now - st.session_state.alert_history['stress_start']).total_seconds() / 60
                if duration > 5:
                    alerts.append({
                        'type': 'warning',
                        'message': f"⚠️ PERINGATAN: Stress terdeteksi selama {duration:.1f} menit!"
                    })
        else:
            st.session_state.alert_history['stress_start'] = None
    
    return alerts

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/heart-monitor.png", width=80)
    st.title("Health Monitor")
    st.markdown("---")
    
    st.header("📡 Connection Status")
    st.success("MQTT Connected")
    st.caption(f"Broker: `{MQTT_BROKER}`")
    st.caption(f"BP Topic: `{MQTT_TOPIC_BP}`")
    st.caption(f"Stress Topic: `{MQTT_TOPIC_STRESS}`")
    
    st.markdown("---")
    st.header("🔧 Service Status")
    try:
        health = requests.get(f"{SERVICE_URL}/health", timeout=2)
        if health.status_code == 200:
            st.success("Service Online")
        else:
            st.error("Service Error")
    except:
        st.error("Service Offline")
    
    st.markdown("---")
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.bp_history = []
        st.session_state.stress_history = []
        st.rerun()

# --- Process Queue from MQTT callbacks ---
# Move data from queue to history
data_received = False

while not shared_data.bp_queue.empty():
    result = shared_data.bp_queue.get()
    print("DEBUG: Pulled BP data from queue")
    st.session_state.bp_result = result
    st.session_state.bp_history.append({
        'timestamp': datetime.now(),
        'prediction': result.get('prediction'),
        'confidence': result.get('confidence'),
        'heart_rate': result.get('heart_rate', {}).get('mean_bpm', 0)
    })
    if len(st.session_state.bp_history) > 20:
        st.session_state.bp_history = st.session_state.bp_history[-20:]
    data_received = True

while not shared_data.stress_queue.empty():
    result = shared_data.stress_queue.get()
    print("DEBUG: Pulled Stress data from queue")
    st.session_state.stress_result = result
    st.session_state.stress_history.append({
        'timestamp': datetime.now(),
        'prediction': result.get('prediction'),
        'confidence': result.get('confidence'),
        'heart_rate': result.get('heart_rate', {}).get('mean_bpm', 0)
    })
    if len(st.session_state.stress_history) > 20:
        st.session_state.stress_history = st.session_state.stress_history[-20:]
    data_received = True

# --- Main Content ---
st.title("🏥 Smart Health Dashboard")
st.markdown("### Real-time Stress & Blood Pressure Detection")

# Check for alerts
alerts = check_alerts()
if alerts:
    for alert in alerts:
        if alert['type'] == 'danger':
            st.markdown(f'<div class="alert-danger">{alert["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-warning">{alert["message"]}</div>', unsafe_allow_html=True)

st.divider()

# Main Results
col1, col2 = st.columns(2)

with col1:
    st.subheader("🩸 Blood Pressure")
    if st.session_state.bp_result:
        bp = st.session_state.bp_result
        pred = bp.get('prediction', 'N/A')
        conf = bp.get('confidence', 0)
        
        # Color coding
        if 'Hypertension' in pred:
            st.error(f"**{pred}**")
        elif 'Hypotension' in pred:
            st.warning(f"**{pred}**")
        elif pred == 'Normal':
            st.success(f"**{pred}**")
        else:
            st.info(f"**{pred}**")
            
        st.metric("Confidence", f"{conf*100:.1f}%")
        
        hr_info = bp.get('heart_rate', {})
        st.metric("Heart Rate (Mean)", f"{hr_info.get('mean_bpm', 0):.1f} BPM")
        
        with st.expander("📊 Detailed BP Stats"):
            st.write(f"**Min BPM:** {hr_info.get('min_bpm', 0):.1f}")
            st.write(f"**Max BPM:** {hr_info.get('max_bpm', 0):.1f}")
            st.write(f"**Std BPM:** {hr_info.get('std_bpm', 0):.1f}")
            st.write(f"**Peaks Detected:** {hr_info.get('num_peaks', 0)}")
            
            probs = bp.get('probabilities', [])
            if probs:
                st.write("**Class Probabilities:**")
                labels = ['Hypotension', 'Normal', 'Elevated', 'Hypertension 1', 'Hypertension 2', 'Crisis']
                for i, prob in enumerate(probs):
                    if i < len(labels):
                        st.write(f"- {labels[i]}: {prob*100:.1f}%")
    else:
        st.info("Waiting for BP data...")

with col2:
    st.subheader("🧠 Stress Level")
    if st.session_state.stress_result:
        stress = st.session_state.stress_result
        pred = stress.get('prediction', 'N/A')
        conf = stress.get('confidence', 0)
        
        # Color coding
        if pred == 'Stress':
            st.error(f"**{pred}**")
        elif pred == 'Baseline':
            st.success(f"**{pred}**")
        else:
            st.info(f"**{pred}**")
            
        st.metric("Confidence", f"{conf*100:.1f}%")
        
        hr_info = stress.get('heart_rate', {})
        st.metric("Heart Rate (Mean)", f"{hr_info.get('mean_bpm', 0):.1f} BPM")
        
        with st.expander("📊 Detailed Stress Stats"):
            st.write(f"**Min BPM:** {hr_info.get('min_bpm', 0):.1f}")
            st.write(f"**Max BPM:** {hr_info.get('max_bpm', 0):.1f}")
            st.write(f"**Std BPM:** {hr_info.get('std_bpm', 0):.1f}")
            st.write(f"**RMSSD (ms):** {hr_info.get('rmssd_ms', 0):.1f}")
            st.write(f"**SDNN (ms):** {hr_info.get('sdnn_ms', 0):.1f}")
            
            probs = stress.get('probabilities', [])
            if probs:
                st.write("**Class Probabilities:**")
                labels = ['Baseline', 'Stress', 'Amusement']
                for i, prob in enumerate(probs):
                    if i < len(labels):
                        st.write(f"- {labels[i]}: {prob*100:.1f}%")
    else:
        st.info("Waiting for Stress data...")

st.divider()

# History Charts
st.subheader("📈 Historical Data")
tab1, tab2 = st.tabs(["Blood Pressure History", "Stress History"])

with tab1:
    if st.session_state.bp_history:
        df_bp = pd.DataFrame(st.session_state.bp_history)
        df_bp['time_str'] = df_bp['timestamp'].dt.strftime('%H:%M:%S')
        
        st.line_chart(df_bp.set_index('timestamp')['heart_rate'])
        
        st.dataframe(
            df_bp[['time_str', 'prediction', 'confidence', 'heart_rate']].rename(columns={
                'time_str': 'Time',
                'prediction': 'Prediction',
                'confidence': 'Confidence',
                'heart_rate': 'Heart Rate'
            }),
            use_container_width=True
        )
    else:
        st.info("No BP history available yet")

with tab2:
    if st.session_state.stress_history:
        df_stress = pd.DataFrame(st.session_state.stress_history)
        df_stress['time_str'] = df_stress['timestamp'].dt.strftime('%H:%M:%S')
        
        st.line_chart(df_stress.set_index('timestamp')['heart_rate'])
        
        st.dataframe(
            df_stress[['time_str', 'prediction', 'confidence', 'heart_rate']].rename(columns={
                'time_str': 'Time',
                'prediction': 'Prediction',
                'confidence': 'Confidence',
                'heart_rate': 'Heart Rate'
            }),
            use_container_width=True
        )
    else:
        st.info("No Stress history available yet")

# Auto-refresh every 2 seconds
time.sleep(2)
st.rerun()

# Auto-refresh
time.sleep(2)
st.rerun()
