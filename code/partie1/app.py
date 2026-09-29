# -*- coding: utf-8 -*-
import os
import sys
import json
import socket
import traceback
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from kafka import KafkaProducer
from pymongo import MongoClient

# Reconfigure stdout/stderr to support utf-8 emojis on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure parent directory is in path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from schema.schema_validator import validate_telemetry
from config import config
from logger import app_logger

# Global in-memory buffers
telemetry_history = []
latest_setup = {"downforce": 50, "engine_mix": 5}

# Initialize Flask app
app = Flask(__name__, static_folder='.', static_url_path='')

# Hardening: Maximum Payload Size Limit
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Hardening: CORS configuration driven by config
if config.CORS_ORIGINS == "*":
    CORS(app)
else:
    CORS(app, origins=config.CORS_ORIGINS)

# Hardening: MongoDB Connection Setup
mongo_client = None
db = None
col_settings = None

try:
    mongo_client = MongoClient(
        config.MONGO_URI,
        serverSelectionTimeoutMS=config.MONGO_CONNECT_TIMEOUT_MS,
        connectTimeoutMS=config.MONGO_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=config.MONGO_SOCKET_TIMEOUT_MS
    )
    mongo_client.admin.command('ping')
    db = mongo_client[config.MONGO_DATABASE]
    col_settings = db['car_settings']
    app_logger.info("Connected to MongoDB at %s", config.mask_secret(config.MONGO_URI))
except Exception as e:
    app_logger.warning("MongoDB connection unavailable (%s). Running without MongoDB.", e)
    mongo_client = None

# Hardening: Kafka Producer Setup
producer = None
try:
    host_port = config.KAFKA_BOOTSTRAP_SERVERS.split(',')[0].strip()
    host_parts = host_port.replace("http://", "").replace("https://", "").split(":")
    k_host = host_parts[0]
    k_port = int(host_parts[1]) if len(host_parts) > 1 else 9092

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    res_code = sock.connect_ex((k_host, k_port))
    sock.close()

    if res_code == 0:
        producer = KafkaProducer(
            bootstrap_servers=[config.KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=config.KAFKA_TIMEOUT_MS,
            max_block_ms=config.KAFKA_TIMEOUT_MS
        )
        app_logger.info("Kafka producer connected to %s", config.KAFKA_BOOTSTRAP_SERVERS)
    else:
        app_logger.info("Kafka broker unreachable on %s:%d (Direct/Offline fallback active)", k_host, k_port)
except Exception as e:
    app_logger.warning("Kafka initialization failed (%s). Fallback active.", e)
    producer = None


# ============================================================================
# ERROR HANDLERS (Hardening: No Stack Trace Leakage)
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    message = getattr(error, 'description', 'Bad Request')
    return jsonify({"status": "error", "message": message}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Resource Not Found"}), 404


@app.errorhandler(413)
def payload_too_large(error):
    return jsonify({"status": "error", "message": "Payload Too Large"}), 413


@app.errorhandler(500)
def internal_server_error(error):
    app_logger.error("Internal Server Error: %s", error)
    return jsonify({"status": "error", "message": "Internal Server Error"}), 500


# ============================================================================
# HEALTH & READINESS ENDPOINTS (Phase 4)
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Liveness probe returning application state."""
    return jsonify({
        "status": "UP",
        "environment": config.FLASK_ENV,
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/readiness', methods=['GET'])
def readiness():
    """Readiness probe evaluating external dependency status."""
    mongo_ok = False
    if mongo_client:
        try:
            mongo_client.admin.command('ping')
            mongo_ok = True
        except Exception:
            mongo_ok = False

    kafka_ok = producer is not None

    if mongo_ok and kafka_ok:
        overall_status = "HEALTHY"
    elif mongo_ok or kafka_ok:
        overall_status = "DEGRADED"
    else:
        overall_status = "DEGRADED" # Direct fallback mode supported

    return jsonify({
        "status": overall_status,
        "dependencies": {
            "mongodb": "CONNECTED" if mongo_ok else "OFFLINE",
            "kafka": "CONNECTED" if kafka_ok else "OFFLINE"
        },
        "timestamp": datetime.now().isoformat()
    }), 200


# ============================================================================
# ROUTE HANDLERS
# ============================================================================

@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/simulation')
def simulation():
    return app.send_static_file('simulation.html')


@app.route('/cockpit')
@app.route('/cockpit/')
def cockpit():
    return app.send_static_file('cockpit/index.html')


@app.route('/setup', methods=['GET'])
def get_setup():
    global latest_setup
    if mongo_client is None or col_settings is None:
        return jsonify(latest_setup), 200
    try:
        latest_doc = col_settings.find_one(sort=[('_id', -1)])
        if latest_doc:
            latest_setup = {
                "downforce": latest_doc.get("downforce", 50),
                "engine_mix": latest_doc.get("engine_mix", 5)
            }
        return jsonify(latest_setup), 200
    except Exception as e:
        app_logger.warning("Error reading setup from MongoDB: %s", e)
        return jsonify(latest_setup), 200


@app.route('/setup', methods=['POST'])
def post_setup():
    global latest_setup
    if not request.is_json:
        return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Malformed JSON payload"}), 400

    try:
        df = int(data.get("downforce", 50))
        em = int(data.get("engine_mix", 5))

        # Range validation
        if not (0 <= df <= 100):
            return jsonify({"status": "error", "message": "downforce must be between 0 and 100"}), 400
        if not (1 <= em <= 10):
            return jsonify({"status": "error", "message": "engine_mix must be between 1 and 10"}), 400

        latest_setup = {"downforce": df, "engine_mix": em}

        if mongo_client and col_settings is not None:
            try:
                col_settings.insert_one({
                    "timestamp": datetime.now().isoformat(),
                    "downforce": df,
                    "engine_mix": em
                })
                app_logger.info("Setup saved to MongoDB")
            except Exception as mongo_err:
                app_logger.warning("Error saving setup to MongoDB: %s", mongo_err)

        app_logger.info("Setup updated: %s", latest_setup)
        return jsonify({"status": "success", "setup": latest_setup}), 200

    except (ValueError, TypeError) as e:
        return jsonify({"status": "error", "message": "Invalid numeric parameter"}), 400
    except Exception as e:
        app_logger.error("Error updating setup: %s", e)
        return jsonify({"status": "error", "message": "Failed to update setup"}), 400


@app.route('/telemetry', methods=['GET'])
def get_telemetry():
    return jsonify(telemetry_history), 200


@app.route('/telemetry', methods=['POST'])
def receive_telemetry():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Malformed JSON payload"}), 400

    # Fast path for connection pings
    if 'ping' in data:
        return jsonify({"status": "success", "ping": True}), 200

    # Enforce Schema V1 validation
    val_res = validate_telemetry(data)
    if not val_res["valid"]:
        app_logger.warning("Schema V1 validation failed: %s", val_res["errors"])
        return jsonify({
            "status": "error",
            "message": "Schema validation failed",
            "errors": val_res["errors"]
        }), 400

    # Store in memory buffer
    telemetry_history.append(data.copy())
    if len(telemetry_history) > 100:
        telemetry_history.pop(0)

    if not producer:
        if mongo_client and db is not None:
            try:
                db['telemetry'].insert_one(data)
                data.pop('_id', None)
                app_logger.debug("Direct DB Fallback insert speed=%.1f", data.get('speed', 0))
                return jsonify({"status": "success", "mode": "direct_mongodb"}), 200
            except Exception as mongo_err:
                app_logger.warning("MongoDB fallback insert error: %s", mongo_err)

        app_logger.debug("Offline Simulator Fallback speed=%.1f", data.get('speed', 0))
        return jsonify({"status": "success", "mode": "offline_console"}), 200

    try:
        producer.send(config.KAFKA_TOPIC, value=data)
        producer.flush()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app_logger.error("Error sending message to Kafka: %s", e)
        return jsonify({"status": "error", "message": "Failed to push telemetry"}), 400


if __name__ == '__main__':
    app_logger.info("Starting Flask application (env=%s, debug=%s, host=%s, port=%d)",
                    config.FLASK_ENV, config.FLASK_DEBUG, config.HOST, config.PORT)
    app.run(host=config.HOST, port=config.PORT, debug=config.FLASK_DEBUG, use_reloader=False)

