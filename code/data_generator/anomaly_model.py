# -*- coding: utf-8 -*-
"""
Deterministic Anomaly Model for F1 Synthetic Data Generator V2
"""

class AnomalyModel:
    @staticmethod
    def evaluate(anomaly_type, lap_progress_pct, timestamp_str):
        """
        Determines if an anomaly condition is active and constructs anomaly payload details.
        Returns:
            dict: {
                "flag": bool,
                "anomalies": list of dicts,
                "is_tire_overheat": bool,
                "is_engine_overheat": bool,
                "is_brake_stress": bool,
                "is_aero_anomaly": bool
            }
        """
        res = {
            "flag": False,
            "anomalies": [],
            "is_tire_overheat": False,
            "is_engine_overheat": False,
            "is_brake_stress": False,
            "is_aero_anomaly": False
        }

        if not anomaly_type:
            return res

        # Activate anomaly during middle 40% of lap progress (pct 30-70%)
        active_window = 30.0 <= (lap_progress_pct % 100.0) <= 70.0

        if not active_window:
            return res

        if anomaly_type == "TIRE_OVERHEAT":
            res["flag"] = True
            res["is_tire_overheat"] = True
            res["anomalies"].append({
                "anomaly_id": f"ANO-TIRE-{int(lap_progress_pct)}",
                "type": "TIRE_OVERHEAT",
                "severity": "WARNING",
                "source": "PHYSICS_ENGINE",
                "affected_component": "TIRE_FL",
                "detected_at": timestamp_str,
                "description": "Front Left tire temperature exceeded 110.0°C thermal limit."
            })
        elif anomaly_type == "ENGINE_OVERHEAT":
            res["flag"] = True
            res["is_engine_overheat"] = True
            res["anomalies"].append({
                "anomaly_id": f"ANO-ENG-{int(lap_progress_pct)}",
                "type": "ENGINE_OVERHEAT",
                "severity": "CRITICAL",
                "source": "PHYSICS_ENGINE",
                "affected_component": "POWERTRAIN",
                "detected_at": timestamp_str,
                "description": "Engine coolant temperature exceeded 120.0°C safety threshold."
            })
        elif anomaly_type == "BRAKE_STRESS":
            res["flag"] = True
            res["is_brake_stress"] = True
            res["anomalies"].append({
                "anomaly_id": f"ANO-BRK-{int(lap_progress_pct)}",
                "type": "BRAKE_STRESS",
                "severity": "WARNING",
                "source": "PHYSICS_ENGINE",
                "affected_component": "BRAKES",
                "detected_at": timestamp_str,
                "description": "Emergency braking stress detected (>4.5G deceleration load)."
            })
        elif anomaly_type == "AERO_ANOMALY":
            res["flag"] = True
            res["is_aero_anomaly"] = True
            res["anomalies"].append({
                "anomaly_id": f"ANO-AERO-{int(lap_progress_pct)}",
                "type": "AERO_ANOMALY",
                "severity": "WARNING",
                "source": "PHYSICS_ENGINE",
                "affected_component": "AERODYNAMICS",
                "detected_at": timestamp_str,
                "description": "Aerodynamic drag anomaly detected (Cd spike +0.12)."
            })

        return res
