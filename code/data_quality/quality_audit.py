# -*- coding: utf-8 -*-
"""
Data Quality Audit Module for F1 Synthetic Telemetry Generator V2
"""

import sys
import os

# Ensure schema validator is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from schema.schema_validator import validate_telemetry


def audit_schema_compliance(events):
    """Measures Schema V1 compliance rate across a dataset of telemetry events."""
    total = len(events)
    if total == 0:
        return {
            "valid_count": 0,
            "invalid_count": 0,
            "compliance_rate_pct": 0.0,
            "sample_errors": []
        }

    # Sample up to 5,000 events if dataset is very large
    sample_events = events if total <= 5000 else events[:5000]

    valid_count = 0
    invalid_count = 0
    errors = []

    for evt in sample_events:
        res = validate_telemetry(evt)
        if res["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
            errors.append({"event_id": evt.get("event_id"), "errors": res["errors"]})

    # Scale counts to total if sampled
    scale_factor = total / len(sample_events)
    total_valid = int(valid_count * scale_factor)
    total_invalid = int(invalid_count * scale_factor)
    compliance_rate = (valid_count / len(sample_events) * 100.0)

    return {
        "valid_count": total_valid,
        "invalid_count": total_invalid,
        "compliance_rate_pct": round(compliance_rate, 2),
        "sample_errors": errors[:5]
    }


def audit_completeness(events):
    """Audits missing or null fields for key telemetry attributes."""
    fields_to_check = [
        "session_id", "event_id", "car_id", "timestamp", "lap_number",
        "sector_number", "throttle", "brake", "fuel_level", "fuel_used",
        "fuel_consumption_rate", "rain_intensity", "track_condition",
        "lap_progress_pct"
    ]
    nested_telemetry = ["speed", "rpm", "gear", "torque", "engine_temperature", "engine_load"]
    nested_tires = ["tire_temp", "tire_wear", "tire_pressure"]

    missing_counts = {f: 0 for f in fields_to_check + nested_telemetry + nested_tires}

    total = len(events)
    for evt in events:
        for f in fields_to_check:
            val = evt.get(f)
            if val is None:
                missing_counts[f] += 1

        tel = evt.get("telemetry", {})
        for f in nested_telemetry:
            if tel.get(f) is None:
                missing_counts[f] += 1

        tires = evt.get("tires", {})
        for f in nested_tires:
            val = tires.get(f)
            if val is None or (isinstance(val, list) and len(val) == 0):
                missing_counts[f] += 1

    missing_rates = {
        f: round((count / total * 100.0), 2) if total > 0 else 0.0
        for f, count in missing_counts.items()
    }

    return {
        "total_events": total,
        "missing_counts": missing_counts,
        "missing_rates_pct": missing_rates
    }


def audit_uniqueness(events):
    """Audits event_id uniqueness and timestamp duplicate detection within sessions."""
    event_ids = [evt.get("event_id") for evt in events if evt.get("event_id")]
    unique_event_ids = set(event_ids)

    duplicate_event_count = len(event_ids) - len(unique_event_ids)

    # Check timestamp duplicates per session
    session_timestamps = {}
    duplicate_timestamp_count = 0

    for evt in events:
        sid = evt.get("session_id")
        ts = evt.get("timestamp")
        if sid not in session_timestamps:
            session_timestamps[sid] = set()
        
        if ts in session_timestamps[sid]:
            duplicate_timestamp_count += 1
        else:
            session_timestamps[sid].add(ts)

    return {
        "total_events": len(events),
        "unique_event_ids_count": len(unique_event_ids),
        "duplicate_event_count": duplicate_event_count,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "uniqueness_rate_pct": round((len(unique_event_ids) / len(events) * 100.0), 2) if events else 0.0
    }


def audit_boundaries(events):
    """Verifies realistic physical numerical bounds."""
    violations = []
    violation_counts = {}

    for evt in events:
        eid = evt.get("event_id", "UNKNOWN")
        speed = evt.get("telemetry", {}).get("speed", 0.0)
        rpm = evt.get("telemetry", {}).get("rpm", 0.0)
        gear = evt.get("telemetry", {}).get("gear", 0)
        throttle = evt.get("throttle", 0.0)
        brake = evt.get("brake", 0.0)
        fuel_level = evt.get("fuel_level", 0.0)
        tires = evt.get("tires", {})
        tire_wears = tires.get("tire_wear", [])

        if not (0.0 <= speed <= 400.0):
            violations.append(f"Event {eid}: speed {speed} out of bounds [0, 400]")
            violation_counts["speed"] = violation_counts.get("speed", 0) + 1

        if not (0.0 <= rpm <= 20000.0):
            violations.append(f"Event {eid}: rpm {rpm} out of bounds [0, 20000]")
            violation_counts["rpm"] = violation_counts.get("rpm", 0) + 1

        if not (-1 <= gear <= 8):
            violations.append(f"Event {eid}: gear {gear} out of bounds [-1, 8]")
            violation_counts["gear"] = violation_counts.get("gear", 0) + 1

        if not (0.0 <= throttle <= 100.0):
            violations.append(f"Event {eid}: throttle {throttle} out of bounds [0, 100]")
            violation_counts["throttle"] = violation_counts.get("throttle", 0) + 1

        if not (0.0 <= brake <= 100.0):
            violations.append(f"Event {eid}: brake {brake} out of bounds [0, 100]")
            violation_counts["brake"] = violation_counts.get("brake", 0) + 1

        if fuel_level < 0.0:
            violations.append(f"Event {eid}: fuel_level {fuel_level} < 0")
            violation_counts["fuel_level"] = violation_counts.get("fuel_level", 0) + 1

        if isinstance(tire_wears, list):
            if len(tire_wears) != 4:
                violations.append(f"Event {eid}: tire_wear length {len(tire_wears)} != 4")
                violation_counts["tire_wear_length"] = violation_counts.get("tire_wear_length", 0) + 1
            for w in tire_wears:
                if not (0.0 <= w <= 100.0):
                    violations.append(f"Event {eid}: tire_wear element {w} out of bounds [0, 100]")
                    violation_counts["tire_wear_bounds"] = violation_counts.get("tire_wear_bounds", 0) + 1

    total = len(events)
    clean_count = total - len(violations)
    boundary_compliance = (clean_count / total * 100.0) if total > 0 else 0.0

    return {
        "total_events": total,
        "total_violations": len(violations),
        "violation_counts_by_field": violation_counts,
        "boundary_compliance_pct": round(max(0.0, boundary_compliance), 2)
    }


def audit_monotonicity(events):
    """Verifies monotonic progression for timestamps, fuel levels, fuel used, and tire wear per session."""
    session_groups = {}
    for evt in events:
        sid = evt.get("session_id")
        if sid not in session_groups:
            session_groups[sid] = []
        session_groups[sid].append(evt)

    timestamp_violations = 0
    fuel_violations = 0
    wear_violations = 0

    for sid, evts in session_groups.items():
        for i in range(1, len(evts)):
            # Timestamp check
            if evts[i].get("timestamp") <= evts[i-1].get("timestamp"):
                timestamp_violations += 1
            
            # Fuel level check (decreasing)
            if evts[i].get("fuel_level", 0.0) > evts[i-1].get("fuel_level", 0.0):
                fuel_violations += 1

            # Tire wear check (non-decreasing)
            w1 = evts[i-1].get("tires", {}).get("tire_wear", [0,0,0,0])[0]
            w2 = evts[i].get("tires", {}).get("tire_wear", [0,0,0,0])[0]
            if w2 < w1:
                wear_violations += 1

    total_checks = sum(len(evts) - 1 for evts in session_groups.values()) if session_groups else 1
    total_violations = timestamp_violations + fuel_violations + wear_violations
    monotonicity_rate = (1.0 - (total_violations / (total_checks * 3.0))) * 100.0 if total_checks > 0 else 100.0

    return {
        "timestamp_violations": timestamp_violations,
        "fuel_monotonicity_violations": fuel_violations,
        "wear_monotonicity_violations": wear_violations,
        "total_checks": total_checks,
        "monotonicity_compliance_pct": round(max(0.0, monotonicity_rate), 2)
    }


def audit_anomalies(events):
    """Reports anomaly occurrences, rate, and active anomaly counts."""
    anomalous_events = [evt for evt in events if evt.get("anomaly_flag")]
    total = len(events)
    rate = (len(anomalous_events) / total * 100.0) if total > 0 else 0.0

    type_counts = {}
    for evt in anomalous_events:
        for a in evt.get("active_anomalies", []):
            atype = a.get("type", "UNKNOWN")
            type_counts[atype] = type_counts.get(atype, 0) + 1

    return {
        "total_events": total,
        "anomalous_events_count": len(anomalous_events),
        "anomaly_rate_pct": round(rate, 2),
        "anomalies_by_type": type_counts
    }


def run_full_quality_audit(events):
    """Runs all quality audits and aggregates objective quality metrics."""
    schema_res = audit_schema_compliance(events)
    comp_res = audit_completeness(events)
    uniq_res = audit_uniqueness(events)
    bound_res = audit_boundaries(events)
    mono_res = audit_monotonicity(events)
    anom_res = audit_anomalies(events)

    return {
        "total_events": len(events),
        "schema_compliance_pct": schema_res["compliance_rate_pct"],
        "completeness_pct": 100.0 - max(comp_res["missing_rates_pct"].values()) if comp_res["missing_rates_pct"] else 100.0,
        "uniqueness_pct": uniq_res["uniqueness_rate_pct"],
        "boundary_compliance_pct": bound_res["boundary_compliance_pct"],
        "monotonicity_compliance_pct": mono_res["monotonicity_compliance_pct"],
        "anomaly_events_count": anom_res["anomalous_events_count"],
        "details": {
            "schema": schema_res,
            "completeness": comp_res,
            "uniqueness": uniq_res,
            "boundaries": bound_res,
            "monotonicity": mono_res,
            "anomalies": anom_res
        }
    }
