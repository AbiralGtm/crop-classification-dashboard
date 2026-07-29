"""Serves the local training-label GeoJSON so the frontend can visualize
where the (currently placeholder) labeled training polygons are located --
useful for sanity-checking that a drawn AOI actually overlaps meaningful
training data before puzzling over a bad classification result.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["labels"])

DEFAULT_LABELS_PATH = (
    Path(__file__).resolve().parents[2] / "training" / "labels" / "rupandehi_crops.geojson"
)


@router.get("/labels")
def get_training_labels() -> dict:
    if not DEFAULT_LABELS_PATH.exists():
        raise HTTPException(status_code=404, detail="No training labels file found")
    with open(DEFAULT_LABELS_PATH) as f:
        return json.load(f)
