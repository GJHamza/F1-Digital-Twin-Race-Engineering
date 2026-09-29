# -*- coding: utf-8 -*-
"""
JSON and Parquet Dataset Serializer for G.4.5.2 Strategy Scenarios.
"""

import os
import json
import pandas as pd
from typing import List, Dict, Any, Union
from ml.strategy.scenario import Scenario
from ml.strategy.stint import Stint
from ml.strategy.pit_stop import PitStop
from datalake.s3_client import get_s3_filesystem


DEFAULT_SCENARIO_STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data_lake", "ml", "strategy", "scenarios")
)


class ScenarioSerializer:
    """
    Handles JSON and Parquet dataset export and import for candidate scenario datasets.
    """

    @staticmethod
    def to_dataframe(scenarios: List[Scenario]) -> pd.DataFrame:
        """
        Converts a list of Scenario objects into a flattened PySpark / Pandas tabular DataFrame.
        """
        records: List[Dict[str, Any]] = []
        for s in scenarios:
            pit_laps = [p.pit_lap for p in s.pit_stops]
            stint_boundaries = [f"{st.start_lap}-{st.end_lap}" for st in s.stints]
            records.append({
                "scenario_id": s.scenario_id,
                "race_id": s.race_id,
                "total_laps": s.total_laps,
                "number_of_stops": s.number_of_stops,
                "number_of_stints": s.number_of_stints,
                "starting_compound": s.starting_compound,
                "compound_sequence_json": json.dumps(s.compound_sequence),
                "pit_laps_json": json.dumps(pit_laps),
                "stint_boundaries_json": json.dumps(stint_boundaries),
                "canonical_key": s.canonical_key,
                "generation_method": s.generation_method,
                "validation_status": s.validation_status,
                "stints_json": json.dumps([st.to_dict() for st in s.stints]),
                "pit_stops_json": json.dumps([p.to_dict() for p in s.pit_stops]),
            })
        return pd.DataFrame(records)

    @classmethod
    def save_json(cls, scenarios: List[Scenario], target_path: str = None) -> str:
        """
        Exports scenario list to a JSON file. Accepts local file path or S3A URI.
        """
        target_path = target_path or os.path.join(DEFAULT_SCENARIO_STORAGE_DIR, "candidate_scenarios.json")
        data = [s.to_dict() for s in scenarios]
        json_str = json.dumps(data, indent=2)

        if target_path.startswith("s3a://") or target_path.startswith("s3://"):
            s3_fs = get_s3_filesystem()
            s3_path = target_path.replace("s3a://", "").replace("s3://", "")
            with s3_fs.open(s3_path, "w") as f:
                f.write(json_str)
        else:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(json_str)

        return target_path

    @classmethod
    def load_json(cls, target_path: str) -> List[Scenario]:
        """
        Loads scenario list from a JSON file.
        """
        if target_path.startswith("s3a://") or target_path.startswith("s3://"):
            s3_fs = get_s3_filesystem()
            s3_path = target_path.replace("s3a://", "").replace("s3://", "")
            with s3_fs.open(s3_path, "r") as f:
                data = json.load(f)
        else:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        scenarios: List[Scenario] = []
        for d in data:
            stints = [
                Stint(
                    stint_id=st["stint_id"],
                    stint_number=st["stint_number"],
                    compound=st["compound"],
                    start_lap=st["start_lap"],
                    end_lap=st["end_lap"],
                    starting_fuel=st["starting_fuel"],
                    ending_fuel=st["ending_fuel"],
                    starting_tire_wear=st["starting_tire_wear"],
                    ending_tire_wear=st["ending_tire_wear"],
                )
                for st in d["stints"]
            ]

            pit_stops = [
                PitStop(
                    pit_stop_id=p["pit_stop_id"],
                    pit_lap=p["pit_lap"],
                    compound_before=p["compound_before"],
                    compound_after=p["compound_after"],
                    stint_before=p["stint_before"],
                    stint_after=p["stint_after"],
                    duration_sec=p["duration_sec"],
                )
                for p in d["pit_stops"]
            ]

            scenarios.append(
                Scenario(
                    scenario_id=d["scenario_id"],
                    race_id=d["race_id"],
                    total_laps=d["total_laps"],
                    starting_compound=d["starting_compound"],
                    compound_sequence=d["compound_sequence"],
                    stints=stints,
                    pit_stops=pit_stops,
                    number_of_stops=d["number_of_stops"],
                    number_of_stints=d["number_of_stints"],
                    generation_method=d.get("generation_method", "BOUNDED_GRID"),
                    validation_status=d.get("validation_status", "VALID"),
                    validation_errors=d.get("validation_errors", []),
                    generation_metadata=d.get("generation_metadata", {}),
                )
            )

        return scenarios

    @classmethod
    def save_parquet(cls, scenarios: List[Scenario], target_path: str = None) -> str:
        """
        Exports scenario list to a Parquet dataset file. Accepts local file path or S3A URI.
        """
        target_path = target_path or os.path.join(DEFAULT_SCENARIO_STORAGE_DIR, "candidate_scenarios.parquet")
        df = cls.to_dataframe(scenarios)

        if target_path.startswith("s3a://") or target_path.startswith("s3://"):
            s3_fs = get_s3_filesystem()
            s3_path = target_path.replace("s3a://", "").replace("s3://", "")
            with s3_fs.open(s3_path, "wb") as f:
                df.to_parquet(f, index=False, engine="pyarrow")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            df.to_parquet(target_path, index=False, engine="pyarrow")

        return target_path
