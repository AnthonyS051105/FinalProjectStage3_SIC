# SIC Stage 3 - Final Project

## Sistem Monitoring Kesehatan Real-time

Deteksi Stress dan Tekanan Darah menggunakan Sensor PPG (MAX30102) dan DHT11.

---

## 📁 Struktur Proyek

```
.
├── firmware/              # Kode ESP32
│   ├── src/
│   │   └── main.cpp      # Program utama ESP32
│   └── platformio.ini    # Konfigurasi PlatformIO
│
├── dashboard/            # Dashboard & Services
│   ├── app_new.py       # Dashboard yang digunakan
│   └── requirements.txt # Python dependencies
│
└── ServiceSICFP/        # AI Service (download dari https://github.com/nafalrust/ServiceSICFP)
```

---

## 🚀 Cara Menjalankan

### 1. Hardware (ESP32)

**Setup:**

1. Buka folder `firmware` di PlatformIO (atau VS Code)
2. Edit `src/main.cpp`:
   - Ubah `ssid` dan `password` WiFi Anda
3. Upload ke ESP32:
   ```bash
   cd firmware
   pio run -t upload
   pio device monitor -b 115200
   ```

**Cara Kerja:**

- ESP32 akan mengumpulkan data selama **10 detik**:
  - PPG @ 100Hz → 1000 samples
  - Temperature @ 4Hz → 40 samples
- Setelah 10 detik, data dikirim via MQTT ke 2 topic:
  - `sic/stage3/bp_data` → untuk prediksi Blood Pressure
  - `sic/stage3/stress_data` → untuk prediksi Stress
- PPG otomatis di-downsample dari 100Hz → 64Hz untuk Stress prediction

---

### 2. Dashboard

**Jalankan Dashboard Baru:**

```bash
cd dashboard
streamlit run app_new.py
```

Dashboard akan otomatis:

1. Subscribe ke MQTT topic `bp_data` dan `stress_data`
2. Kirim data ke service
3. Tampilkan hasil prediksi:
   - **Blood Pressure:** Hypotension, Normal, Elevated, Hypertension 1/2, Crisis
   - **Stress:** Baseline, Stress, Amusement
4. Menampilkan Heart Rate statistics (mean, min, max, std, RMSSD, SDNN)
5. **Alert System:** Peringatan otomatis jika hipertensi/hipotensi/stress berlangsung > 5 menit

---

## 📊 Format Data

### Hardware → MQTT (BP Data)

```json
{
  "ppg": [array of 1000 PPG values @ 100Hz],
  "device_id": "ESP32_SIC_01",
  "timestamp": 123456
}
```

### Hardware → MQTT (Stress Data)

```json
{
  "ppg": [array of 640 PPG values @ 64Hz],
  "temperature": [array of 40 temperature values @ 4Hz],
  "device_id": "ESP32_SIC_01",
  "timestamp": 123456
}
```

### Service → Dashboard (Response)

```json
{
  "prediction": "Normal",
  "class_id": 1,
  "confidence": 0.92,
  "probabilities": [0.02, 0.92, 0.03, 0.02, 0.01, 0.0],
  "heart_rate": {
    "mean_bpm": 72.5,
    "std_bpm": 3.2,
    "min_bpm": 68.0,
    "max_bpm": 78.0,
    "num_peaks": 12
  },
  "features_extracted": 17
}
```

---

## 🔧 Konfigurasi

### Ubah MQTT Broker (jika perlu)

Di `firmware/src/main.cpp`:

```cpp
const char* mqtt_server = "broker.hivemq.com"; // Ganti dengan IP lokal jika perlu
```

Di `dashboard/app_new.py`:

```python
MQTT_BROKER = "broker.hivemq.com"
```

### Ubah Service URL

Di `dashboard/app_new.py`:

```python
SERVICE_URL = "http://localhost:5000"  # Ganti dengan URL service real
```

---

## 🧪 Testing

1. **Test Hardware Only (tanpa WiFi):**

   - Hardware otomatis masuk **Simulation Mode** jika WiFi gagal
   - Data dummy akan dicetak di Serial Monitor

2. **Test dengan Mock Service:**

   - Jalankan `mock_service.py`
   - Jalankan `app_new.py`
   - Upload program ke ESP32
   - Dashboard akan menampilkan prediksi dummy

3. **Test dengan Real Service:**
   - Ganti `SERVICE_URL` di `app_new.py` ke service asli
   - Jalankan service asli dari folder `ServiceSICFP/`

---

## 📝 Catatan Penting

1. **Downsampling PPG:** Dilakukan di hardware (ESP32) menggunakan decimation sederhana
2. **Alert System:** Threshold 5 menit bisa diubah di `app_new.py` (search `duration > 5`)
3. **Buffer Size:** MQTT buffer sudah diperbesar di ESP32 (`setBufferSize(16384)`)
4. **Auto-refresh:** Dashboard auto-refresh setiap 2 detik

---

## 🐛 Troubleshooting

**WiFi tidak connect?**

- Pastikan SSID & password benar (case-sensitive)
- ESP32 hanya support 2.4GHz (bukan 5GHz)
- Cek sinyal WiFi dengan WiFi Scanner di Serial Monitor

**MQTT publish gagal?**

- Cek ukuran pesan (max ~16KB)
- Cek koneksi internet
- Gunakan broker lokal jika broker publik lambat

**Dashboard tidak update?**

- Cek apakah Mock Service berjalan
- Cek Service URL di `app_new.py`
- Lihat error di terminal tempat mock_service.py berjalan

---

## 👥 Tim

- **Hardware & Firmware:** [Yohanes Anthony Saputra]
- **AI Model & Backend:** [Muhammad Nafal Rustanto]
- **Dashboard:** [Yohanes Anthony Saputra]
- **Elektronis** [Alfito Putra Parindra]
- **Laporan Project** [Amelia Ocha Maharani]

---

Semoga sukses dengan Final Project-nya! 🎉
