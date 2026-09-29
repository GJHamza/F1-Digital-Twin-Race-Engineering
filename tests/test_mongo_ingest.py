# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Phase G.2.4 — MongoDB Telemetry Data Architecture.
Ensures valid insertion, schema rejection, idempotency, session/anomaly derivation,
index creation, and legacy document safety without touching production Atlas.
"""

import sys
import os
import pytest
from datetime import datetime, timezone

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from storage.mongo_client import ensure_indexes
from storage.mongo_ingest import TelemetryIngestor
from data_generator.generator_v2 import SyntheticGeneratorV2


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.indexes = {}

    def create_index(self, keys, name=None, unique=False, sparse=False):
        idx_name = name or "_".join(f"{k}_{v}" for k, v in keys)
        self.indexes[idx_name] = {"keys": keys, "unique": unique, "sparse": sparse}
        return idx_name

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("InsertResult", (), {"inserted_id": doc.get("_id", "mock_id")})()

    def insert_many(self, docs, ordered=True):
        inserted = []
        for d in docs:
            self.docs.append(dict(d))
            inserted.append(d.get("_id", "mock_id"))
        return type("InsertManyResult", (), {"inserted_ids": inserted})()

    def bulk_write(self, operations, ordered=False):
        inserted_count = 0
        upserted_count = 0

        for op in operations:
            op_type = op.__class__.__name__
            if op_type == "InsertOne":
                self.docs.append(dict(op._doc))
                inserted_count += 1
            elif op_type == "UpdateOne":
                filter_dict = op._filter
                update_dict = op._doc
                is_upsert = op._upsert

                # Search existing
                match_idx = -1
                for idx, doc in enumerate(self.docs):
                    matches = True
                    for k, v in filter_dict.items():
                        if doc.get(k) != v:
                            matches = False
                            break
                    if matches:
                        match_idx = idx
                        break

                if match_idx >= 0:
                    # Update existing
                    if "$set" in update_dict:
                        self.docs[match_idx].update(update_dict["$set"])
                else:
                    if is_upsert:
                        new_doc = dict(filter_dict)
                        if "$set" in update_dict:
                            new_doc.update(update_dict["$set"])
                        if "$setOnInsert" in update_dict:
                            new_doc.update(update_dict["$setOnInsert"])
                        self.docs.append(new_doc)
                        upserted_count += 1

        return type("BulkWriteResult", (), {
            "inserted_count": inserted_count,
            "upserted_count": upserted_count,
            "modified_count": 0,
            "deleted_count": 0
        })()

    def find(self, filter_dict=None):
        filter_dict = filter_dict or {}
        results = []
        for doc in self.docs:
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc)
        return results

    def find_one(self, filter_dict=None):
        res = self.find(filter_dict)
        return res[0] if res else None

    def count_documents(self, filter_dict=None):
        return len(self.find(filter_dict))


class MockDatabase:
    def __init__(self, name="F1_Simulation"):
        self.name = name
        self.collections = {}

    def __getitem__(self, item):
        if item not in self.collections:
            self.collections[item] = MockCollection(item)
        return self.collections[item]


@pytest.fixture
def mock_db():
    db = MockDatabase("F1_Simulation")
    # Pre-populate legacy car_settings collection
    db["car_settings"].insert_one({"car_id": "SIM-CAR-01", "downforce": 50, "engine_mix": 5})
    # Pre-populate legacy telemetry document without event_id
    db["telemetry"].insert_one({"speed": 280.0, "rpm": 12000, "legacy": True})
    return db


@pytest.fixture
def ingestor(mock_db):
    return TelemetryIngestor(db=mock_db, batch_size=100)


@pytest.fixture
def sample_events():
    gen = SyntheticGeneratorV2(seed=42)
    return gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=2)


def test_index_creation(mock_db):
    res = ensure_indexes(mock_db)
    assert "telemetry" in res
    assert "sessions" in res
    assert "anomalies" in res

    tel_indexes = mock_db["telemetry"].indexes
    assert "idx_session_timestamp" in tel_indexes
    assert "idx_car_timestamp_desc" in tel_indexes
    assert "idx_event_id_unique" in tel_indexes

    ses_indexes = mock_db["sessions"].indexes
    assert "idx_session_id_unique" in ses_indexes
    assert ses_indexes["idx_session_id_unique"]["unique"] is True


def test_valid_telemetry_insertion(ingestor, sample_events, mock_db):
    report = ingestor.ingest_events(sample_events)
    assert report["valid_count"] == len(sample_events)
    assert report["rejected_count"] == 0
    assert report["inserted_count"] == len(sample_events)
    # Total telemetry docs should be 1 legacy doc + inserted sample events
    assert mock_db["telemetry"].count_documents() == len(sample_events) + 1


def test_invalid_telemetry_rejection(ingestor, sample_events, mock_db):
    invalid_event = dict(sample_events[0])
    invalid_event["throttle"] = 150.0  # Out of bounds (> 100)

    events_to_test = sample_events[:5] + [invalid_event]
    report = ingestor.ingest_events(events_to_test)

    assert report["total_processed"] == 6
    assert report["valid_count"] == 5
    assert report["rejected_count"] == 1
    assert report["inserted_count"] == 5
    assert len(report["rejected_sample"]) == 1


def test_idempotent_repeated_ingestion(ingestor, sample_events, mock_db):
    # First ingestion
    report1 = ingestor.ingest_events(sample_events)
    count1 = mock_db["telemetry"].count_documents()

    # Second ingestion of exact same events
    report2 = ingestor.ingest_events(sample_events)
    count2 = mock_db["telemetry"].count_documents()

    assert count1 == count2
    assert report2["duplicate_skipped_count"] == len(sample_events)
    assert report2["inserted_count"] == 0


def test_session_creation_and_derivation(ingestor, sample_events, mock_db):
    report = ingestor.ingest_events(sample_events)
    assert report["sessions_upserted"] == 2
    assert mock_db["sessions"].count_documents() == 2

    session_doc = mock_db["sessions"].find_one({"session_id": sample_events[0]["session_id"]})
    assert session_doc is not None
    assert session_doc["laps_completed"] == 2
    assert session_doc["scenario"] == "RACE_DRY"
    assert session_doc["car_id"] == "SIM-CAR-01"
    assert "started_at" in session_doc
    assert "ended_at" in session_doc


def test_anomaly_creation_and_deduplication(ingestor, mock_db):
    gen = SyntheticGeneratorV2(seed=42)
    anomaly_events = gen.generate_dataset("TIRE_OVERHEAT", sessions_count=1, laps_per_session=2)

    report1 = ingestor.ingest_events(anomaly_events)
    anom_count1 = mock_db["anomalies"].count_documents()
    assert anom_count1 > 0

    # Repeat ingestion should not duplicate anomalies
    report2 = ingestor.ingest_events(anomaly_events)
    anom_count2 = mock_db["anomalies"].count_documents()
    assert anom_count1 == anom_count2


def test_legacy_collection_and_document_safety(ingestor, sample_events, mock_db):
    # Verify legacy car_settings exists before
    assert mock_db["car_settings"].count_documents() == 1
    legacy_telemetry = mock_db["telemetry"].find_one({"legacy": True})
    assert legacy_telemetry is not None

    ingestor.ingest_events(sample_events)

    # Verify legacy car_settings remains intact
    assert mock_db["car_settings"].count_documents() == 1
    # Verify legacy telemetry doc without event_id is preserved
    assert mock_db["telemetry"].find_one({"legacy": True}) is not None


def test_bulk_ingestion_performance_and_metrics(ingestor, mock_db):
    gen = SyntheticGeneratorV2(seed=42)
    large_sample = gen.generate_dataset("RACE_DRY", sessions_count=5, laps_per_session=5)  # 1,500 evts

    report = ingestor.ingest_events(large_sample)
    assert report["total_processed"] == 1500
    assert report["valid_count"] == 1500
    assert report["inserted_count"] == 1500
    assert report["duration_sec"] > 0
    assert report["events_per_sec"] > 0
