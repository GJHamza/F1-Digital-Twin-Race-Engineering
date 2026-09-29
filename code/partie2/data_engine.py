# -*- coding: utf-8 -*-
"""
Data Engine Consumer for F1 Digital Twin
Listens to Kafka telemetry topic and persists validated records to MongoDB.
"""

import sys
import os
import json
from kafka import KafkaConsumer
from pymongo import MongoClient

# Reconfigure stdout/stderr to support utf-8 emojis on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure parent path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import config
from logger import app_logger


def run_data_engine():
    """Runs the Kafka to MongoDB ingestion loop."""
    app_logger.info("Starting Data Engine Service...")
    app_logger.info("Target MongoDB: %s", config.mask_secret(config.MONGO_URI))
    app_logger.info("Target Kafka Broker: %s (Topic: %s)", config.KAFKA_BOOTSTRAP_SERVERS, config.KAFKA_TOPIC)

    try:
        # MongoDB Connection
        client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=config.MONGO_CONNECT_TIMEOUT_MS,
            connectTimeoutMS=config.MONGO_CONNECT_TIMEOUT_MS
        )
        client.admin.command('ping')
        db = client[config.MONGO_DATABASE]
        collection = db['telemetry']
        app_logger.info("Connected to MongoDB database '%s'", config.MONGO_DATABASE)

        # Kafka Consumer Configuration
        consumer = KafkaConsumer(
            config.KAFKA_TOPIC,
            bootstrap_servers=[config.KAFKA_BOOTSTRAP_SERVERS],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id=config.KAFKA_GROUP_ID,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            request_timeout_ms=config.KAFKA_TIMEOUT_MS
        )

        app_logger.info("Kafka Consumer online. Listening for telemetry messages...")

        for message in consumer:
            telemetry_data = message.value
            if not isinstance(telemetry_data, dict):
                app_logger.warning("Skipping non-dict telemetry payload: %s", telemetry_data)
                continue

            result = collection.insert_one(telemetry_data)
            vitesse = telemetry_data.get('speed', 0)
            vent = telemetry_data.get('wind_speed', 0)
            app_logger.debug("Telemetry inserted speed=%.1f km/h wind=%.1f km/h -> Mongo ID: %s",
                             vitesse, vent, result.inserted_id)

    except KeyboardInterrupt:
        app_logger.info("Data Engine stopped by user.")
        sys.exit(0)
    except Exception as e:
        app_logger.error("Data Engine critical error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_data_engine()