# -*- coding: utf-8 -*-
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from data_generator.physics_model import (
    calculate_vehicle_mass,
    calculate_speed_and_inputs,
    calculate_gear_and_rpm,
    calculate_powertrain,
    calculate_aerodynamics,
    calculate_tires,
    calculate_fuel,
    calculate_track_position
)

def test_calculate_vehicle_mass():
    mass = calculate_vehicle_mass(798.0, 80.0)
    assert mass == 878.0
    mass_empty = calculate_vehicle_mass(798.0, 0.0)
    assert mass_empty == 798.0

def test_speed_and_inputs_bounds():
    for pct in range(0, 101, 10):
        speed, throttle, brake, steering = calculate_speed_and_inputs(float(pct))
        assert 0.0 <= speed <= 360.0
        assert 0.0 <= throttle <= 100.0
        assert 0.0 <= brake <= 100.0
        assert -360.0 <= steering <= 360.0

def test_gear_and_rpm_derivation():
    gear_idle, rpm_idle = calculate_gear_and_rpm(0.0, 0.0)
    assert gear_idle == 0
    assert rpm_idle == 1000.0

    gear_top, rpm_top = calculate_gear_and_rpm(340.0, 100.0)
    assert gear_top == 8
    assert 12000.0 <= rpm_top <= 15000.0

def test_aerodynamics_downforce_velocity_dependence():
    cd1, df1 = calculate_aerodynamics(100.0, 10.0)
    cd2, df2 = calculate_aerodynamics(200.0, 10.0)
    # Downforce scales quadratically with speed
    assert df2 > df1 * 3.0

def test_tire_arrays_length_four_and_monotonic_wear():
    temps1, wears1, press1, deg1 = calculate_tires(200.0, 0.0, 1)
    temps2, wears2, press2, deg2 = calculate_tires(200.0, 0.0, 10)
    
    assert len(temps1) == 4
    assert len(wears1) == 4
    assert len(press1) == 4
    
    # Tire wear increases with lap age
    assert wears2[0] > wears1[0]

def test_fuel_level_monotonicity():
    fuel1, used1, rate1 = calculate_fuel(100.0, 1, 0.0)
    fuel2, used2, rate2 = calculate_fuel(100.0, 5, 50.0)
    
    assert fuel2 < fuel1
    assert used2 > used1
    assert fuel2 >= 0.0

def test_track_position_calculation():
    x1, z1 = calculate_track_position(0.0)
    x2, z2 = calculate_track_position(50.0)
    assert isinstance(x1, float)
    assert isinstance(z1, float)
    assert (x1, z1) != (x2, z2)
