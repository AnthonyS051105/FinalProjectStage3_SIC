import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import pandas as pd
from dummy_model import HealthClassifier

# --- Dashboard UI Configuration (Must be first) ---
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
    </style>
    """, unsafe_allow_html=True)

# --- Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "sic/stage3/data"

# --- Initialize Model ---
classifier = HealthClassifier()

# --- Session State for History ---
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['time', 'heart_rate', 'spo2', 'temperature'])

if 'mqtt_data' not in st.session_state:
    st.session_state.mqtt_data = {
        "heart_rate": 0,
        "spo2": 0,
        "temperature": 0,
        "device_id": "Waiting..."
    }

# --- MQTT Setup ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        st.session_state.mqtt_data = payload
        
        # Update history
        new_row = {
            'time': pd.Timestamp.now(),
            'heart_rate': payload.get('heart_rate', 0),
            'spo2': payload.get('spo2', 0),
            'temperature': payload.get('temperature', 0)
        }
        # Append new row
        st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True)
        
        # Keep only last 50 records to keep it fast
        if len(st.session_state.history) > 50:
            st.session_state.history = st.session_state.history.iloc[-50:]
            
    except Exception as e:
        print(f"Error parsing JSON: {e}")

@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
        
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    return client

client = start_mqtt()

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/heart-monitor.png", width=80)
    st.title("Health Monitor")
    st.markdown("---")
    st.header("📡 Connection Status")
    st.success("MQTT Connected")
    st.caption(f"Broker: `{MQTT_BROKER}`")
    st.caption(f"Topic: `{MQTT_TOPIC}`")
    
    st.markdown("---")
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.history = pd.DataFrame(columns=['time', 'heart_rate', 'spo2', 'temperature'])
        st.rerun()

# --- Main Content ---
st.title("🏥 Smart Health Dashboard")
st.markdown("### Real-time Stress & Blood Pressure Detection")

# Get latest data
data = st.session_state.mqtt_data
hr = data.get("heart_rate", 0)
spo2 = data.get("spo2", 0)
temp = data.get("temperature", 0)

# Predictions
stress_class = classifier.predict_stress(hr, spo2, temp)
bp_class = classifier.predict_bp(hr, spo2, temp)

# Top Metrics Row
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("❤️ Heart Rate", f"{hr} BPM")
with col2:
    st.metric("💧 SpO2", f"{spo2} %")
with col3:
    st.metric("🌡️ Temperature", f"{temp} °C")

st.divider()

# Classification Results with Color Coding
c1, c2 = st.columns(2)

with c1:
    st.subheader("🧠 Stress Level")
    if stress_class == "Stress":
        st.error(f"⚠️ {stress_class}")
    elif stress_class == "Amusement":
        st.info(f"😄 {stress_class}")
    else:
        st.success(f"😌 {stress_class}")

with c2:
    st.subheader("🩸 Blood Pressure")
    if "Hipertensi" in bp_class:
        st.warning(f"⚠️ {bp_class}")
    elif bp_class == "Hipotensi":
        st.info(f"⬇️ {bp_class}")
    else:
        st.success(f"✅ {bp_class}")

st.divider()

# Charts
st.subheader("📈 Live Trends")
tab1, tab2 = st.tabs(["Heart Rate & SpO2", "Temperature"])

with tab1:
    if not st.session_state.history.empty:
        chart_data = st.session_state.history[['time', 'heart_rate', 'spo2']].set_index('time')
        st.line_chart(chart_data)
    else:
        st.info("Waiting for data...")

with tab2:
    if not st.session_state.history.empty:
        chart_data = st.session_state.history[['time', 'temperature']].set_index('time')
        st.line_chart(chart_data, color="#FF5733")
    else:
        st.info("Waiting for data...")

# Raw Data Expander
with st.expander("🔍 View Raw Data Payload"):
    st.json(data)

# Auto-refresh logic
time.sleep(1)
st.rerun()

# Raw Data Expander
with st.expander("🔍 View Raw Data Payload"):
    st.json(data)

# Auto-refresh logic
time.sleep(1)
st.rerun()
