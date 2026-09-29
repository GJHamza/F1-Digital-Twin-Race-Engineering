# -*- coding: utf-8 -*-
"""
MongoDB Client & Index Management Module for F1 Digital Twin
Provides standard MongoDB connections and idempotent index creation.
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

# Load environment variables from project root .env
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

DEFAULT_DB_NAME = "F1_Simulation"


def get_mongo_client(uri=None):
    """
    Returns a PyMongo MongoClient instance.
    Defaults to MONGO_URI environment variable or localhost.
    """
    if uri is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000)


def get_database(client=None, db_name=DEFAULT_DB_NAME, uri=None):
    """
    Returns a reference to the specified MongoDB Database.
    """
    if client is None:
        client = get_mongo_client(uri=uri)
    return client[db_name]


def ensure_indexes(db):
    """
    Ensures all required indexes exist idempotently across sessions, telemetry, and anomalies.
    Does not drop existing legacy indexes or collections.
    Returns:
        dict: Summary of created/confirmed index names per collection.
    """
    results = {}

    # 1. Telemetry Indexes
    col_telemetry = db["telemetry"]
    idx_tel_1 = col_telemetry.create_index(
        [("session_id", ASCENDING), ("timestamp", ASCENDING)],
        name="idx_session_timestamp"
    )
    idx_tel_2 = col_telemetry.create_index(
        [("car_id", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_car_timestamp_desc"
    )
    # Sparse unique index on event_id for Schema V1 telemetry idempotency (ignores legacy docs without event_id)
    idx_tel_3 = col_telemetry.create_index(
        [("event_id", ASCENDING)],
        name="idx_event_id_unique",
        unique=True,
        sparse=True
    )
    results["telemetry"] = [idx_tel_1, idx_tel_2, idx_tel_3]

    # 2. Sessions Indexes
    col_sessions = db["sessions"]
    idx_ses_1 = col_sessions.create_index(
        [("session_id", ASCENDING)],
        name="idx_session_id_unique",
        unique=True
    )
    idx_ses_2 = col_sessions.create_index(
        [("created_at", DESCENDING)],
        name="idx_session_created_at"
    )
    results["sessions"] = [idx_ses_1, idx_ses_2]

    # 3. Anomalies Indexes
    col_anomalies = db["anomalies"]
    idx_anom_1 = col_anomalies.create_index(
        [("session_id", ASCENDING), ("severity", ASCENDING)],
        name="idx_anomaly_session_severity"
    )
    idx_anom_2 = col_anomalies.create_index(
        [("session_id", ASCENDING), ("event_id", ASCENDING)],
        name="idx_anomaly_session_event_unique",
        unique=True,
        sparse=True
    )
    results["anomalies"] = [idx_anom_1, idx_anom_2]

    return results
