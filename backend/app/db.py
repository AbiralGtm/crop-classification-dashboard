"""SQLite-backed persistence for AOI classification jobs.

Replaces the original in-memory dict store, which lost every job the moment
the backend process restarted -- fine for the very first smoke test, not for
anything you'd want to revisit later (which is the whole point of an AOI
history list). Swap for PostGIS if/when multi-user concurrent access or
spatial queries over AOI history are needed -- see the project plan's tech
stack notes; SQLite is enough for local/single-user use.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

Base = declarative_base()


class AOIJobRecord(Base):
    __tablename__ = "aoi_jobs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    request_json = Column(Text, nullable=False)  # serialized AOIRequest
    status = Column(String, nullable=False)
    result_json = Column(Text, nullable=True)  # serialized result dict
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _make_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


engine = _make_engine()
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
