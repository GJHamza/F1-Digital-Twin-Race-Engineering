# -*- coding: utf-8 -*-
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from data_generator.generator_v2 import SyntheticGeneratorV2
from data_quality.quality_audit import (
    audit_schema_compliance,
    audit_completeness,
    audit_uniqueness,
    audit_boundaries,
    audit_monotonicity,
    audit_anomalies,
    run_full_quality_audit
)
from data_quality.statistical_audit import (
    extract_numeric_dataframe,
    calculate_statistical_summary,
    calculate_pearson_correlations,
    analyze_scenario_differentiation,
    generate_offline_plots
)

@pytest.fixture(scope="module")
def sample_events():
    gen = SyntheticGeneratorV2(seed=42)
    return gen.generate_dataset("RACE_DRY", sessions_count=1, laps_per_session=2)

def test_audit_schema_compliance(sample_events):
    res = audit_schema_compliance(sample_events)
    assert res["compliance_rate_pct"] == 100.0
    assert res["invalid_count"] == 0

def test_audit_completeness(sample_events):
    res = audit_completeness(sample_events)
    assert res["total_events"] == len(sample_events)
    for f, rate in res["missing_rates_pct"].items():
        assert rate == 0.0, f"Field {f} has missing rate {rate}%"

def test_audit_uniqueness(sample_events):
    res = audit_uniqueness(sample_events)
    assert res["duplicate_event_count"] == 0
    assert res["duplicate_timestamp_count"] == 0
    assert res["uniqueness_rate_pct"] == 100.0

def test_audit_boundaries(sample_events):
    res = audit_boundaries(sample_events)
    assert res["total_violations"] == 0
    assert res["boundary_compliance_pct"] == 100.0

def test_audit_monotonicity(sample_events):
    res = audit_monotonicity(sample_events)
    assert res["timestamp_violations"] == 0
    assert res["fuel_monotonicity_violations"] == 0
    assert res["wear_monotonicity_violations"] == 0

def test_audit_anomalies(sample_events):
    gen = SyntheticGeneratorV2(seed=42)
    anom_events = gen.generate_dataset("TIRE_OVERHEAT", sessions_count=1, laps_per_session=2)
    res = audit_anomalies(anom_events)
    assert res["anomalous_events_count"] > 0
    assert "TIRE_OVERHEAT" in res["anomalies_by_type"]

def test_run_full_quality_audit(sample_events):
    report = run_full_quality_audit(sample_events)
    assert report["schema_compliance_pct"] == 100.0
    assert report["completeness_pct"] == 100.0
    assert report["uniqueness_pct"] == 100.0
    assert report["boundary_compliance_pct"] == 100.0
    assert report["monotonicity_compliance_pct"] == 100.0

def test_calculate_statistical_summary(sample_events):
    df = extract_numeric_dataframe(sample_events)
    stats = calculate_statistical_summary(df)
    assert "speed" in stats
    assert stats["speed"]["count"] == len(sample_events)
    assert stats["speed"]["min"] >= 0.0
    assert stats["speed"]["max"] <= 400.0

def test_calculate_pearson_correlations(sample_events):
    df = extract_numeric_dataframe(sample_events)
    corrs = calculate_pearson_correlations(df)
    assert len(corrs) > 0
    for item in corrs:
        assert -1.0 <= item["pearson_r"] <= 1.0

def test_scenario_differentiation():
    gen = SyntheticGeneratorV2(seed=42)
    events_dry = gen.generate_dataset("QUALIFYING_DRY", sessions_count=1, laps_per_session=1)
    events_rain = gen.generate_dataset("HEAVY_RAIN", sessions_count=1, laps_per_session=1)
    combined = events_dry + events_rain
    diff = analyze_scenario_differentiation(combined)
    
    assert "QUALIFYING" in diff or len(diff) >= 1

def test_generate_offline_plots(sample_events, tmp_path):
    out_dir = str(tmp_path / "plots")
    success = generate_offline_plots(sample_events, output_dir=out_dir)
    assert success is True
    assert os.path.exists(os.path.join(out_dir, "speed_distribution.png"))
    assert os.path.exists(os.path.join(out_dir, "tire_wear_progression.png"))
    assert os.path.exists(os.path.join(out_dir, "downforce_vs_speed.png"))
