# Crop Classification Dashboard

Satellite-imagery crop classification for the Rupandehi District pilot (Terai plains, Lumbini Province, Nepal), built on Google Earth Engine, FastAPI, and Next.js. See `project_plan.md` for the full architecture/roadmap; this README covers how to run what's scaffolded so far.

The pilot region was moved here from an earlier Pokhara Valley target: Rupandehi's flat, large, rectangular Terai fields are a much better match for Sentinel-2's 10m pixels than Pokhara's small hillside terraces, and it's where Nepal's actual institutional crop-mapping program (ICIMOD/SERVIR-HKH with the Ministry of Agriculture and Livestock Development) has done real field data collection. See `project_plan.md` section 3 for details and sources.

## Status

This is a Phase 0/1 scaffold: the API, GEE pipeline, and dashboard UI are wired end-to-end, but the training labels (`backend/training/labels/rupandehi_crops.geojson`) are **64 synthetic placeholder polygons (8 per crop class), not real ground truth** — they were programmatically scattered across Rupandehi farmland to give the accuracy evaluation feature enough points per class to produce a number at all, not to be trustworthy. Replace them before trusting any classification output — see the labeling notes in `project_plan.md` section 3.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Google Cloud project registered for Earth Engine access (free, noncommercial tier): https://code.earthengine.google.com/register

## Backend setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit GEE_PROJECT_ID with your registered Cloud project id
earthengine authenticate   # one-time browser login for local dev
uvicorn app.main:app --reload --port 8000
```

API docs will be at http://localhost:8000/docs once running.

### Building real training data

```bash
# 1. Replace backend/training/labels/rupandehi_crops.geojson with real, field-verified
#    or carefully hand-digitized field polygons (see project_plan.md for label sources —
#    ICIMOD/SERVIR-HKH and the RicePAL project are the two concrete leads found so far).
# 2. Extract features for one crop season at a time (Rupandehi has a monsoon rice season
#    and a separate winter/rabi wheat-lentil-mustard season):
python training/extract_training_data.py \
  --labels training/labels/rupandehi_crops.geojson \
  --start 2025-11-01 --end 2026-03-01 \
  --out data/samples/rupandehi_winter_samples.csv

# 3. Compare Random Forest vs XGBoost and get accuracy metrics:
python training/train_model.py \
  --data data/samples/rupandehi_winter_samples.csv \
  --out data/models/rupandehi_rf.joblib
```

Live inference (the `/aoi` endpoint) trains a `smileRandomForest` classifier directly in Earth Engine from the labels file each time, so no model file needs to be loaded into the API — `train_model.py` is for offline experimentation/accuracy reporting, and its winning feature set is mirrored in `app/gee/features.py`.

## Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # defaults to http://localhost:8000
npm run dev
```

Open http://localhost:3000, draw a polygon/rectangle over Rupandehi's farmland (the map opens centered there, with a satellite base layer and the placeholder training labels visible as an overlay), pick a date range, and click Classify.

## Repo layout

```
backend/
  app/
    gee/          GEE auth, Sentinel-2 imagery + indices + terrain + phenology, sampling/classification
    ml/            inference.py wraps the GEE classifier for the API
    routers/       /aoi (+history), /classify, /results, /export, /crops, /labels
    models/        pydantic request/response schemas
    db.py           SQLAlchemy engine/model for SQLite-backed job persistence
    store.py        AOI job CRUD + history, backed by db.py
    reference_data.py  hardcoded Rupandehi district statistics for the scale check
  training/         offline feature extraction + RF/XGBoost model comparison scripts
  data/             samples/ (extracted CSVs) and models/ (saved .joblib, for reference)
frontend/
  app/              Next.js app-router pages
  components/       Map.tsx (Leaflet + draw + satellite/training-label layers), Dashboard.tsx (charts + accuracy + district check), HistoryPanel.tsx, ExportPanel.tsx
  lib/               api.ts (typed fetch wrappers), palette.ts (shared crop-class colors)
docs/diagrams/       black-and-white SVG diagrams (system architecture, model training
                     pipeline, training-data labels, task pipeline, org/roles charts)
project_plan.md      full architecture, roadmap, and risk notes
```

## Accuracy reporting

Every classification also runs a held-out validation: the labeled training points are randomly split, a separate classifier is trained on one part and tested on the other, and overall accuracy, kappa, and per-class precision/recall are shown in the dashboard under "Held-out accuracy". This never touches the classifier used to produce the actual map — it's purely diagnostic. With 8 points per class the split will usually produce *a* number now (rather than the "not available" message from a 1-point-per-class set), but it's still a smoke test, not a trustworthy accuracy figure — see `backend/app/gee/features.py:evaluate_classifier`.

## Phenology features

Classification no longer relies on a single averaged composite alone. `backend/app/gee/imagery.py:get_monthly_ndvi_image` builds one NDVI band per calendar month in the request's date range (`ndvi_m0`, `ndvi_m1`, ...), and `app/gee/features.py:build_feature_image` stacks those onto the base spectral/index/terrain bands. This lets the classifier see *when* a field greens up and senesces, not just its average state — important for Rupandehi since a monsoon crop (rice) and a winter crop (wheat/lentil/mustard) can occupy the same plot in different parts of the year. Both the offline training scripts and the live classifier use this same feature stack, so a model trained from an exported CSV matches what's actually served.

## AOI history

Classification jobs now persist to SQLite (`backend/app/store.py`, `backend/app/db.py`) instead of an in-memory dict, so they survive a backend restart. The frontend sidebar shows a "Past AOIs" list (`GET /aoi`); clicking one reloads its geometry, date range, and full result (thumbnail, stats, accuracy) without resubmitting to Earth Engine.

## District scale check

Results also include a rough sanity check against Nepal's published district-level statistics: Rupandehi's total major-cereal area (92,967 ha combined across paddy/maize/wheat/millet/barley/buckwheat, MoALD FY 2079/80) is hardcoded in `backend/app/reference_data.py`, and the dashboard shows what percentage of that your AOI's predicted cropped area represents. This is deliberately coarse — it's a scale check ("is this AOI plausible relative to the whole district," not "is each crop type correct") — see the caveats in `reference_data.py`.

## ESA WorldCereal label integration

Training no longer relies solely on the manual placeholder polygons. `backend/app/gee/worldcereal.py` pulls real per-pixel points from ESA WorldCereal (`ESA/WorldCereal/2021/MODELS/v100` in the GEE Data Catalog): confident (>=70%) `temporarycrops`, `maize`, and `wintercereals` pixels are stratified-sampled and mapped onto this app's `non_crop` / `maize` / `wheat` classes, then merged with the manual labels before training (`app/gee/features.py:classify_aoi`, `include_worldcereal=True` by default). This only covers 3 of the 8 target classes — rice, sugarcane, lentil, mustard, and vegetables still have no ready-made per-pixel source and need manual digitizing or ICIMOD/RicePAL data (see project_plan.md section 3).

## Sentinel-1 SAR fallback

`backend/app/gee/imagery.py:get_sentinel1_composite` adds a median VV/VH Sentinel-1 composite to the feature stack alongside the Sentinel-2 composite and phenology bands (`app/gee/features.py:build_feature_image`). Since radar sees through cloud cover, this gives the classifier a usable signal even when the monsoon-season Sentinel-2 composite has cloud gaps.

## GeoTIFF export

`GET /export/{aoi_id}/geotiff` is now implemented — it redirects to a GeoTIFF download URL generated by Earth Engine at classification time (`app/ml/inference.py:_geotiff_download_url_safely`, same synchronous `getDownloadURL` pattern already used for the PNG thumbnail). Works for AOI sizes this pilot targets; very large AOIs would need an async `Export.image.toDrive`/`toCloudStorage` task instead.

## Known gaps / next steps

- Training labels for rice, sugarcane, lentil, mustard, and vegetables are still synthetic placeholders (64 points, not field-verified) — WorldCereal now covers non_crop/maize/wheat, but the rest remain the critical labeling path (see project_plan.md section 3 and 10).
- SQLite persistence is single-file/single-process — swap for PostGIS before multi-user concurrent use (see `backend/app/db.py`).
- The district comparison is a district-wide, six-crop-combined total, not a per-crop breakdown — a real per-crop reference would need deeper extraction from the MoALD statistical book's detailed tables.
- GeoTIFF export only works synchronously for AOIs under GEE's per-request pixel limit; no async export task yet for larger areas.
- `npm install` / `pip install` need to be run in your own environment — dependency versions are pinned but not installed/verified against a live GEE project from this scaffold (the non-GEE parts — schemas, SQLite store, FastAPI app wiring — were verified directly in a sandbox with real installs during development; the WorldCereal/SAR/GeoTIFF code was verified by import/compile checks and against the GEE Data Catalog docs, not a live GEE run).

## License

MIT — see `LICENSE`.
