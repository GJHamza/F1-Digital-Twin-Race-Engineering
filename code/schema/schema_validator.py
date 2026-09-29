# -*- coding: utf-8 -*-
import os
import json
import jsonschema

SCHEMA_FILE_PATH = os.path.join(os.path.dirname(__file__), 'schema_v1.json')

_cached_schema = None
_cached_validator = None

def load_schema():
    global _cached_schema, _cached_validator
    if _cached_schema is None:
        if not os.path.exists(SCHEMA_FILE_PATH):
            raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE_PATH}")
        with open(SCHEMA_FILE_PATH, 'r', encoding='utf-8') as f:
            _cached_schema = json.load(f)
            _cached_validator = jsonschema.Draft7Validator(_cached_schema)
    return _cached_schema, _cached_validator

def validate_telemetry(payload):
    """
    Validates a telemetry payload against Schema V1.
    Returns:
        dict: {
            "valid": bool,
            "errors": list of str
        }
    Never raises an uncaught exception to caller.
    """
    if not isinstance(payload, dict):
        return {
            "valid": False,
            "errors": ["Payload must be a JSON object (dict)."]
        }
        
    try:
        _, validator = load_schema()
        errors = []
        for error in validator.iter_errors(payload):
            # Format clean user-friendly error path and message
            path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            errors.append(f"Field '{path}': {error.message}")
            
        if errors:
            return {
                "valid": False,
                "errors": errors
            }
            
        return {
            "valid": True,
            "errors": []
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Schema validator error: {str(e)}"]
        }
