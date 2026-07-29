from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class AOIRequest(BaseModel):
    name: str = Field(..., description="Human-readable label for this AOI")
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry (Polygon)")
    start_date: date
    end_date: date
    labels_source: str = Field(
        default="local:training/labels/rupandehi_crops.geojson",
        description=(
            "GEE asset id, or 'local:<path>' pointing at a GeoJSON labeled "
            "FeatureCollection used to train the classifier for this run."
        ),
    )


class AOIResponse(BaseModel):
    aoi_id: str
    status: JobStatus


class ClassStat(BaseModel):
    class_id: int
    class_name: str
    area_hectares: float


class AccuracyPerClass(BaseModel):
    class_name: str
    recall: float | None = None
    precision: float | None = None


class AccuracyStats(BaseModel):
    """Held-out validation accuracy from a random train/test split of the
    labeled training points -- see app/gee/features.py:evaluate_classifier.
    `available=False` means the split was too degenerate to mean anything
    (currently expected, given only a handful of placeholder labels)."""

    available: bool
    train_count: int | None = None
    test_count: int | None = None
    overall_accuracy: float | None = None
    kappa: float | None = None
    per_class: list[AccuracyPerClass] = []
    note: str | None = None
    reason: str | None = None


class DistrictComparison(BaseModel):
    """Rough sanity check of the AOI's total predicted cropped area against
    Rupandehi district's published major-cereal area -- see
    app/reference_data.py. Not a per-crop validation, just a scale check."""

    district_name: str
    district_major_cereal_area_ha: float | None = None
    fiscal_year: str | None = None
    source: str | None = None
    aoi_cropped_area_ha: float | None = None
    aoi_pct_of_district_cereal_area: float | None = None
    note: str | None = None


class ClassificationResult(BaseModel):
    aoi_id: str
    status: JobStatus
    thumbnail_url: str | None = None
    geotiff_url: str | None = None
    class_stats: list[ClassStat] = []
    accuracy: AccuracyStats | None = None
    district_comparison: DistrictComparison | None = None
    error: str | None = None


class AOIHistoryItem(BaseModel):
    """Lightweight summary of a past AOI request, for the history list.
    Includes the original geometry so the frontend can redraw it on the map
    and re-fetch the full result (thumbnail/stats/accuracy) on selection."""

    aoi_id: str
    name: str
    status: JobStatus
    start_date: date
    end_date: date
    geometry: dict[str, Any]
    created_at: datetime
