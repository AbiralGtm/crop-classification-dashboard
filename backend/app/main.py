from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import aoi, classify, export, labels

settings = get_settings()

app = FastAPI(
    title="Crop Classification API",
    description="Satellite imagery crop classification for the Rupandehi District pilot (and beyond).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aoi.router)
app.include_router(classify.router)
app.include_router(export.router)
app.include_router(labels.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}
