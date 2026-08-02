"""AOI job persistence, backed by SQLite (see app/db.py).

Replaces the earlier in-memory dict, which lost all history on every backend
restart. Function signatures match the old in-memory version so the routers
that already call create_job/set_status/set_result/set_error/get_job didn't
need to change; list_jobs() is new, for the AOI history endpoint.
"""
import json
import uuid

from app.db import AOIJobRecord, SessionLocal
from app.models.schemas import AOIRequest, JobStatus


def create_job(request: AOIRequest) -> str:
    aoi_id = str(uuid.uuid4())
    with SessionLocal() as session:
        record = AOIJobRecord(
            id=aoi_id,
            name=request.name,
            request_json=request.model_dump_json(),
            status=JobStatus.pending.value,
        )
        session.add(record)
        session.commit()
    return aoi_id


def set_status(aoi_id: str, status: JobStatus) -> None:
    with SessionLocal() as session:
        record = session.get(AOIJobRecord, aoi_id)
        if record:
            record.status = status.value
            session.commit()


def set_result(aoi_id: str, result: dict) -> None:
    with SessionLocal() as session:
        record = session.get(AOIJobRecord, aoi_id)
        if record:
            record.result_json = json.dumps(result)
            record.status = JobStatus.done.value
            session.commit()


def set_error(aoi_id: str, error: str) -> None:
    with SessionLocal() as session:
        record = session.get(AOIJobRecord, aoi_id)
        if record:
            record.error = error
            record.status = JobStatus.failed.value
            session.commit()


def get_job(aoi_id: str) -> dict | None:
    with SessionLocal() as session:
        record = session.get(AOIJobRecord, aoi_id)
        if record is None:
            return None
        return _record_to_dict(record)


def list_jobs(limit: int = 50) -> list[dict]:
    """Most recent AOI jobs first, for the history list."""
    with SessionLocal() as session:
        records = (
            session.query(AOIJobRecord)
            .order_by(AOIJobRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_record_to_dict(r) for r in records]


def _record_to_dict(record: AOIJobRecord) -> dict:
    return {
        "aoi_id": record.id,
        "name": record.name,
        "request": AOIRequest.model_validate_json(record.request_json),
        "status": JobStatus(record.status),
        "result": json.loads(record.result_json) if record.result_json else None,
        "error": record.error,
        "created_at": record.created_at,
    }
