import random

class HealthClassifier:
    def __init__(self):
        self.stress_classes = ["Baseline", "Stress", "Amusement"]
        self.bp_classes = ["Hipotensi", "Normal", "Pre-hipertensi", "Hipertensi 1", "Hipertensi 2"]

    def predict_stress(self, heart_rate, spo2, temperature):
        """
        Dummy logic for Stress Classification.
        Real model would use HRV features, etc.
        """
        # Simple dummy rules
        if heart_rate > 90:
            return "Stress"
        elif heart_rate < 65:
            return "Amusement"
        else:
            return "Baseline"

    def predict_bp(self, heart_rate, spo2, temperature):
        """
        Dummy logic for Blood Pressure Classification.
        """
        # Randomly return a class for demonstration purposes, 
        # or use simple logic:
        if heart_rate > 100:
            return "Hipertensi 1"
        elif heart_rate > 110:
            return "Hipertensi 2"
        elif heart_rate < 60:
            return "Hipotensi"
        else:
            return "Normal"
