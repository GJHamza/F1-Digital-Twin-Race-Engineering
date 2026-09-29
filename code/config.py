# -*- coding: utf-8 -*-
"""
Centralized Application Configuration for F1 Digital Twin
Provides environment-based configuration management for Flask, MongoDB, Kafka, MinIO, and Logging.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class AppConfig:
    """Production and Security Hardened Configuration Class."""

    def __init__(self):
        # Environment mode
        self.FLASK_ENV = os.getenv("FLASK_ENV", "production").lower()
        self.FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "t", "yes")

        # Network settings
        self.HOST = os.getenv("HOST", "127.0.0.1" if self.FLASK_ENV == "production" else "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "5000"))
        
        # CORS Security settings
        cors_raw = os.getenv(
            "CORS_ORIGINS", 
            "http://localhost:5000,http://127.0.0.1:5000,http://localhost:3000,http://localhost:8501"
        )
        if cors_raw.strip() == "*":
            if self.FLASK_ENV == "production":
                # Restrict wildcard CORS in production to safe defaults
                self.CORS_ORIGINS = [
                    "http://localhost:5000",
                    "http://127.0.0.1:5000",
                    "http://localhost:3000",
                    "http://localhost:8501"
                ]
            else:
                self.CORS_ORIGINS = "*"
        else:
            self.CORS_ORIGINS = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]

        # Content limits
        self.MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(1 * 1024 * 1024))) # 1 MB default

        # MongoDB Settings
        self.MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.MONGO_DATABASE = os.getenv("MONGO_DATABASE", "F1_Simulation")
        self.MONGO_CONNECT_TIMEOUT_MS = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "1000"))
        self.MONGO_SOCKET_TIMEOUT_MS = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "1000"))

        # Kafka Settings
        self.KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", os.getenv("KAFKA_BROKER", "localhost:9092"))
        self.KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "f1_telemetry")
        self.KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "f1-engine-group")
        self.KAFKA_TIMEOUT_MS = int(os.getenv("KAFKA_TIMEOUT_MS", "1000"))

        # MinIO / S3 Settings
        self.MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        self.MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
        self.MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        self.MINIO_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")

        # Logging Settings
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    def get_log_level(self):
        """Returns python logging level constant."""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(self.LOG_LEVEL, logging.INFO)

    def mask_secret(self, text: str) -> str:
        """Masks sensitive credentials or passwords in a string."""
        if not text:
            return ""
        if "://" in text and "@" in text:
            # Mask URI like mongodb://user:pass@host
            scheme, rest = text.split("://", 1)
            credentials, host = rest.split("@", 1)
            return f"{scheme}://***:***@{host}"
        return text

    def to_dict(self, mask_secrets: bool = True) -> dict:
        """Serializes config options to dictionary format."""
        return {
            "FLASK_ENV": self.FLASK_ENV,
            "FLASK_DEBUG": self.FLASK_DEBUG,
            "HOST": self.HOST,
            "PORT": self.PORT,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "MAX_CONTENT_LENGTH": self.MAX_CONTENT_LENGTH,
            "MONGO_URI": self.mask_secret(self.MONGO_URI) if mask_secrets else self.MONGO_URI,
            "MONGO_DATABASE": self.MONGO_DATABASE,
            "KAFKA_BOOTSTRAP_SERVERS": self.KAFKA_BOOTSTRAP_SERVERS,
            "KAFKA_TOPIC": self.KAFKA_TOPIC,
            "KAFKA_GROUP_ID": self.KAFKA_GROUP_ID,
            "MINIO_ENDPOINT": self.MINIO_ENDPOINT,
            "MINIO_BUCKET": self.MINIO_BUCKET,
            "LOG_LEVEL": self.LOG_LEVEL
        }


# Global singleton instance
config = AppConfig()
