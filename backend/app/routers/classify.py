"""Re-classification and supported-crop-class endpoints.

Initial classification happens automatically when an AOI is submitted
(see routers/aoi.py). This router lets the frontend re-run classification
against the same AOI/date range (e.g. after updating training labels or
swapping model parameters) without resubmitting the AOI geometry.
"""
import traceback

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.config import get_settings
from app.models.schemas import ClassificationResult, JobStatus
from app import store
from app.routers.aoi import resolve_labels_source, run_job

router = APIRouter(tags=["classify"])


@router.post("/classify/{aoi_id}", response_model=ClassificationResult)
def reclassify(aoi_id: str, background_tasks: BackgroundTasks) -> ClassificationResult:
    job = store.get_job(aoi_id)
    if job is None:
        raise HTTPException(status_code=404, detail="AOI job not found")

    request = job["request"]
    store.set_status(aoi_id, JobStatus.pending)
    background_tasks.add_task(run_job, aoi_id, request)
    return ClassificationResult(aoi_id=aoi_id, status=JobStatus.pending)


@router.get("/results/{aoi_id}", response_model=ClassificationResult)
def get_results(aoi_id: str) -> ClassificationResult:
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


@router.get("/crops")
def list_crops() -> list[str]:
    return get_settings().crop_classes
