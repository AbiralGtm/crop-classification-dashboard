"""AOI submission + classification job endpoints.

Classification runs in a FastAPI BackgroundTask for the MVP. Swap for
Celery + Redis (per the project plan) once AOI sizes/date ranges grow large
enough that requests risk exceeding request-handler timeouts.
"""
import json
import traceback

import ee
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.gee.auth import init_earth_engine
from app.ml.inference import run_classification
from app.models.schemas import (
    AOIHistoryItem,
    AOIRequest,
    AOIResponse,
    ClassificationResult,
    JobStatus,
)
from app import store

router = APIRouter(prefix="/aoi", tags=["aoi"])


def resolve_labels_source(labels_source: str):
    if labels_source.startswith("local:"):
        path = labels_source.removeprefix("local:")
        with open(path) as f:
            return json.load(f)
    return labels_source


def run_job(aoi_id: str, request: AOIRequest) -> None:
    try:
        store.set_status(aoi_id, JobStatus.running)
        init_earth_engine()
        geometry = ee.Geometry(request.geometry)
        labels_source = resolve_labels_source(request.labels_source)
        result = run_classification(
            geometry=geometry,
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            labels_source=labels_source,
        )
        store.set_result(aoi_id, result)
    except Exception as exc:  # noqa: BLE001
        store.set_error(aoi_id, f"{exc}\n{traceback.format_exc()}")


@router.post("", response_model=AOIResponse)
def submit_aoi(request: AOIRequest, background_tasks: BackgroundTasks) -> AOIResponse:
    aoi_id = store.create_job(request)
    background_tasks.add_task(run_job, aoi_id, request)
    return AOIResponse(aoi_id=aoi_id, status=JobStatus.pending)


@router.get("", response_model=list[AOIHistoryItem])
def list_aoi_history(limit: int = 50) -> list[AOIHistoryItem]:
    """Past AOI requests, most recent first -- includes the original geometry
    so the frontend can redraw it on the map; fetch /aoi/{id}/status
    separately for the full result (thumbnail/stats/accuracy)."""
    jobs = store.list_jobs(limit=limit)
    return [
        AOIHistoryItem(
            aoi_id=j["aoi_id"],
            name=j["name"],
            status=j["status"],
            start_date=j["request"].start_date,
            end_date=j["request"].end_date,
            geometry=j["request"].geometry,
            created_at=j["created_at"],
        )
        for j in jobs
    ]


@router.get("/{aoi_id}/status", response_model=ClassificationResult)
def get_aoi_status(aoi_id: str) -> ClassificationResult:
    job = store.get_job(aoi_id)
    if job is None:
        raise HTTPException(status_code=404, detail="AOI job not found")

    result = job.get("result") or {}
    return ClassificationResult(
        aoi_id=aoi_id,
        status=job["status"],
        thumbnail_url=result.get("thumbnail_url"),
        geotiff_url=result.get("geotiff_url"),
        class_stats=result.get("class_stats", []),
        accuracy=result.get("accuracy"),
        district_comparison=result.get("district_comparison"),
        error=job.get("error"),
    )
