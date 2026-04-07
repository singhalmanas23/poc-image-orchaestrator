"""
Simple image storage — saves generated images locally with metadata.
In production, swap this for S3/GCS.
"""

import json
import os
from datetime import datetime

from app.config import get_settings


_image_store: dict[str, dict] = {}


def save_result(image_id: str, result: dict) -> None:
    """Save image result metadata to in-memory store."""
    _image_store[image_id] = {
        **result,
        "created_at": datetime.utcnow().isoformat(),
    }


def get_result(image_id: str) -> dict | None:
    """Retrieve image result by ID."""
    return _image_store.get(image_id)


def list_results(limit: int = 20) -> list[dict]:
    """List recent image results."""
    items = list(_image_store.values())
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]
