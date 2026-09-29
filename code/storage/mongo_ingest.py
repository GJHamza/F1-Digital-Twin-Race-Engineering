# -*- coding: utf-8 -*-
"""
MongoDB Telemetry Data Ingestion Pipeline for F1 Digital Twin
Provides offline bulk JSONL / list ingestion with Schema V1 validation,
session & anomaly derivation, and idempotent upserts.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pymongo import UpdateOne, InsertOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

# Ensure parent directory is in path for schema validator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from schema.schema_validator import validate_telemetry
from storage.mongo_client import get_database, ensure_indexes


class TelemetryIngestor:
    """
    Offline Telemetry Ingestion Pipeline.
    Enforces Schema V1 validation, idempotent telemetry storage,
    session document derivation, and anomaly extraction.
    """

    def __init__(self, db=None, batch_size=1000):
        self.db = db if db is not None else get_database()
        ensure_indexes(self.db)
        self.batch_size = batch_size

    def ingest_jsonl(self, filepath):
        """
        Reads a JSONL file line-by-line, parses JSON, and ingests telemetry events.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"JSONL file not found at {filepath}")

        events = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        return self.ingest_events(events)

    def ingest_events(self, events):
        """
        Ingests a list of telemetry events into MongoDB.
        Returns detailed ingestion report metrics.
        """
        t0 = time.time()

        total_processed = len(events)
        valid_events = []
        rejected_events = []

        # 1. Schema Validation Phase
        for evt in events:
            val_res = validate_telemetry(evt)
            if val_res["valid"]:
                valid_events.append(evt)
            else:
                rejected_events.append({
                    "event_id": evt.get("event_id", "UNKNOWN"),
                    "errors": val_res["errors"]
                })

        valid_count = len(valid_events)
        rejected_count = len(rejected_events)

        if valid_count == 0:
            t1 = time.time()
            return {
                "total_processed": total_processed,
                "valid_count": 0,
                "rejected_count": rejected_count,
                "inserted_count": 0,
                "duplicate_skipped_count": 0,
                "sessions_upserted": 0,
                "anomalies_upserted": 0,
                "duration_sec": round(t1 - t0, 3),
                "events_per_sec": 0.0,
                "rejected_sample": rejected_events[:5]
            }

        # 2. Derive & Upsert Session Documents
        sessions_count = self._ingest_sessions(valid_events)

        # 3. Derive & Upsert Anomaly Documents
        anomalies_count = self._ingest_anomalies(valid_events)

        # 4. Bulk Idempotent Telemetry Ingestion
        inserted_count, duplicate_skipped_count = self._ingest_telemetry_bulk(valid_events)

        t1 = time.time()
        duration = t1 - t0
        evts_per_sec = total_processed / duration if duration > 0 else 0.0

        return {
            "total_processed": total_processed,
            "valid_count": valid_count,
            "rejected_count": rejected_count,
            "inserted_count": inserted_count,
            "duplicate_skipped_count": duplicate_skipped_count,
            "sessions_upserted": sessions_count,
            "anomalies_upserted": anomalies_count,
            "duration_sec": round(duration, 3),
            "events_per_sec": round(evts_per_sec, 1),
            "rejected_sample": rejected_events[:5]
        }

    def _ingest_sessions(self, valid_events):
        """Groups events by session_id and upserts session metadata documents."""
        session_groups = {}
        for evt in valid_events:
            sid = evt.get("session_id")
            if not sid:
                continue
            if sid not in session_groups:
                session_groups[sid] = []
            session_groups[sid].append(evt)

        operations = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for sid, evts in session_groups.items():
            first = evts[0]
            timestamps = [e.get("timestamp") for e in evts if e.get("timestamp")]
            started_at = min(timestamps) if timestamps else now_iso
            ended_at = max(timestamps) if timestamps else now_iso
            laps = [e.get("lap_number", 1) for e in evts]
            max_laps = max(laps) if laps else 1

            session_doc = {
                "session_id": sid,
                "car_id": first.get("car_id", "SIM-CAR-01"),
                "team": first.get("team", "Scuderia Ferrari"),
                "driver_id": first.get("driver_id", "LEC-16"),
                "session_type": first.get("session_type", "RACE"),
                "created_at": started_at,
                "started_at": started_at,
                "ended_at": ended_at,
                "laps_completed": max_laps,
                "scenario": first.get("scenario", "RACE_DRY"),
                "schema_version": "1.0"
            }

            operations.append(
                UpdateOne({"session_id": sid}, {"$set": session_doc}, upsert=True)
            )

        if operations:
            self.db["sessions"].bulk_write(operations, ordered=False)

        return len(session_groups)

    def _ingest_anomalies(self, valid_events):
        """Extracts active anomalies from events and upserts into anomalies collection."""
        operations = []
        for evt in valid_events:
            if not evt.get("anomaly_flag"):
                continue

            sid = evt.get("session_id")
            eid = evt.get("event_id")
            car_id = evt.get("car_id")
            ts = evt.get("timestamp")

            for a in evt.get("active_anomalies", []):
                atype = a.get("type", "UNKNOWN_ANOMALY")
                severity = a.get("severity", "HIGH")
                desc = a.get("description", "Telemetry anomaly detected")

                anomaly_doc = {
                    "schema_version": "1.0",
                    "session_id": sid,
                    "event_id": eid,
                    "car_id": car_id,
                    "timestamp": ts,
                    "severity": severity,
                    "anomaly_type": atype,
                    "description": desc,
                    "active": True
                }

                # Idempotent match on session_id + event_id + anomaly_type
                filter_key = {"session_id": sid, "event_id": eid, "anomaly_type": atype}
                operations.append(
                    UpdateOne(filter_key, {"$set": anomaly_doc}, upsert=True)
                )

        if operations:
            self.db["anomalies"].bulk_write(operations, ordered=False)

        return len(operations)

    def _ingest_telemetry_bulk(self, valid_events):
        """
        Bulk inserts valid telemetry documents into 'telemetry' collection.
        Uses UpdateOne with $setOnInsert for idempotent unique insertion by event_id.
        """
        inserted_count = 0
        duplicate_skipped_count = 0

        # Chunk into batches
        for i in range(0, len(valid_events), self.batch_size):
            batch = valid_events[i:i + self.batch_size]
            operations = []
            for evt in batch:
                eid = evt.get("event_id")
                if eid:
                    # Idempotent upsert: if event_id already exists, $setOnInsert does nothing
                    operations.append(
                        UpdateOne({"event_id": eid}, {"$setOnInsert": evt}, upsert=True)
                    )
                else:
                    # Legacy fallback without event_id: direct insert
                    operations.append(InsertOne(evt))

            if operations:
                try:
                    res = self.db["telemetry"].bulk_write(operations, ordered=False)
                    inserted_count += (res.upserted_count + res.inserted_count)
                    duplicate_skipped_count += (len(batch) - (res.upserted_count + res.inserted_count))
                except BulkWriteError as bwe:
                    # Handle duplicate key errors gracefully
                    upserted = bwe.details.get("nUpserted", 0)
                    inserted = bwe.details.get("nInserted", 0)
                    inserted_count += (upserted + inserted)
                    duplicate_skipped_count += (len(batch) - (upserted + inserted))

        return inserted_count, duplicate_skipped_count
