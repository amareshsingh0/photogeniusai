"""
Generation Event Logger
Helper module for services to log generation events for monitoring.
Uses local/EFS storage (DATA_DIR); no Modal. AWS-compatible.
"""

from datetime import datetime
from typing import Dict, Optional
import json

from .storage import metrics_volume


def log_generation(
    user_id: str,
    generation_id: str,
    mode: str,
    time_seconds: float,
    status: str = "completed",  # completed, failed
    similarity: Optional[float] = None,
    quality_score: Optional[float] = None,
    cost: float = 0.0,
    identity_id: Optional[str] = None,
    error_type: Optional[str] = None,
    rating: Optional[str] = None,  # up, down
    metadata: Optional[Dict] = None,
):
    """
    Log a generation event for monitoring.

    Call this from orchestrator/identity engine after each generation.

    Args:
        user_id: User identifier
        generation_id: Generation job ID
        mode: Generation mode (REALISM, CREATIVE, etc.)
        time_seconds: Generation time in seconds
        status: Status (completed, failed)
        similarity: Face similarity score (0-1) if applicable
        quality_score: Overall quality score if applicable
        cost: Cost in USD
        identity_id: Identity ID if used
        error_type: Error type if failed
        rating: User rating (up, down)
        metadata: Additional metadata
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "generation_id": generation_id,
        "mode": mode,
        "time_seconds": time_seconds,
        "status": status,
        "similarity": similarity,
        "quality_score": quality_score,
        "cost": cost,
        "identity_id": identity_id,
        "error_type": error_type,
        "rating": rating,
        "metadata": metadata or {},
    }

    try:
        logs_file = "/data/generation_logs.json"

        # Load existing logs
        logs = []
        if metrics_volume.exists(logs_file):
            try:
                with metrics_volume.open(logs_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        # Append new log
        logs.append(log_entry)

        # Keep only last 10000 entries (prune old logs)
        if len(logs) > 10000:
            logs = logs[-10000:]

        # Save
        with metrics_volume.open(logs_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    except Exception as e:
        print(f"Warning: Failed to log generation event: {e}")


def log_refinement(
    user_id: str,
    refinement_id: str,
    original_generation_id: str,
    time_seconds: float,
    status: str = "completed",
    cost: float = 0.0,
    metadata: Optional[Dict] = None,
):
    """Log a refinement event"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "refinement_id": refinement_id,
        "original_generation_id": original_generation_id,
        "time_seconds": time_seconds,
        "status": status,
        "cost": cost,
        "event_type": "refinement",
        "metadata": metadata or {},
    }

    try:
        logs_file = "/data/generation_logs.json"
        logs = []
        if metrics_volume.exists(logs_file):
            try:
                with metrics_volume.open(logs_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        logs.append(log_entry)
        if len(logs) > 10000:
            logs = logs[-10000:]

        with metrics_volume.open(logs_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    except Exception as e:
        print(f"Warning: Failed to log refinement event: {e}")
