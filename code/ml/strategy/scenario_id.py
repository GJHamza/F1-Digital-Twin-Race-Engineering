# -*- coding: utf-8 -*-
"""
Canonical Key Representation and Deterministic Scenario ID Generator for G.4.5.2.
"""

import hashlib
from typing import List
from ml.strategy.stint import Stint


def generate_canonical_key(stints: List[Stint]) -> str:
    """
    Generates a canonical string representation for a stint sequence.
    Format: COMPOUND_1:START_1-END_1|COMPOUND_2:START_2-END_2|...

    Example:
        SOFT:1-20|MEDIUM:21-50

    Args:
        stints: Ordered list of Stint objects.

    Returns:
        Canonical key string.
    """
    if not stints:
        raise ValueError("Cannot generate canonical key for empty stint list")

    sorted_stints = sorted(stints, key=lambda s: s.stint_number)
    tokens = [f"{s.compound.upper()}:{s.start_lap}-{s.end_lap}" for s in sorted_stints]
    return "|".join(tokens)


def generate_deterministic_scenario_id(race_id: str, canonical_key: str) -> str:
    """
    Generates a deterministic SHA-256 scenario ID from race_id and canonical_key.
    Format: SCN_<SHA256[:12]>

    Example:
        SCN_a8f3b9c1d2e4

    Args:
        race_id: Race configuration identifier.
        canonical_key: Strategy canonical key string.

    Returns:
        Deterministic scenario ID string.
    """
    if not race_id:
        raise ValueError("race_id cannot be empty")
    if not canonical_key:
        raise ValueError("canonical_key cannot be empty")

    raw_input = f"{race_id}::{canonical_key}".encode("utf-8")
    hash_hex = hashlib.sha256(raw_input).hexdigest()[:12]
    return f"SCN_{hash_hex}"
