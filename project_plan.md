# Crop Classification Dashboard — Project Plan

## 1. Goal

A web dashboard where a user draws/selects a location, pulls Sentinel-2 satellite imagery for that area and time range via Google Earth Engine (GEE), runs a trained crop classification model, and displays the results as a map layer with summary stats and exportable reports. Multi-region, multi-crop, production-leaning tool.

**Pilot region: Rupandehi District, Lumbini Province, Nepal (Terai plains, near Siddharthanagar/Bhairahawa).** The project initially targeted Pokhara Valley (mountainous terrace agriculture); it was moved to Rupandehi because Terai fields are large, flat, and rectangular — a much better match for Sentinel-2's 10m pixels than Pokhara's small hillside terraces — and because Rupandehi is where Nepal's actual institutional crop-mapping program has done real field data collection (see section 3). Main crops: rice (monsoon/kharif season, roughly Jun–Nov), wheat, lentil and mustard (winter/rabi season, roughly Nov–Mar), plus maize, sugarcane, and vegetables. Pokhara's crop calendar and terrain-driven challenges remain documented below and in section 10 for reference, since the same architecture applies to either region.

## 2. Architecture

```
┌─────────────────────────┐      ┌──────────────────────────┐      ┌────────────────────┐
│   Frontend (Next.js)     │─────▶│   Backend API (FastAPI)   │─────▶│  Google Earth Engine │
│   Map draw/select AOI    │      │   /aoi /classify /export  │      │  Sentinel-2 imagery  │
│   Results overlay        │◀─────│   Model inference          │◀─────│  + label datasets     │
│   Charts / export UI     │      │   Job queue for long runs  │      └────────────────────┘
└─────────────────────────┘      └──────────────────────────┘
                                          │
                                          ▼
                                 ┌──────────────────┐
                                 │  Model artifacts   │
                                 │  (RF/XGBoost .pkl) │
                                 │  + PostGIS/S3 for   │
                                 │  results & reports  │
                                 └──────────────────┘
```

- **Frontend**: Next.js + a map library (Mapbox GL or Leaflet) for AOI drawing, layer display, and results dashboard (charts via Recharts/Chart.js).
- **Backend**: FastAPI (Python) — owns the GEE session, feature extraction, model inference, and report generation. Long-running jobs (large AOIs, multi-date composites) go through a background task queue (Celery + Redis, or simpler `BackgroundTasks` for MVP).
- **ML layer**: scikit-learn/XGBoost model trained offline on labeled pixels, loaded by the backend for inference on new AOIs.
- **Storage**: PostGIS (or SQLite+GeoAlchemy for MVP) for AOI history and classification results; local/S3 storage for generated report files (PDF/GeoTIFF/CSV).

## 3. Data Pipeline

**Imagery source**: Sentinel-2 Level-2A (surface reflectance), 10–20m resolution, via GEE's `COPERNICUS/S2_SR_HARMONIZED` collection. Note GEE now requires a registered Google Cloud project with a chosen noncommercial quota tier (mandatory since mid-2024, tiers enforced since April 2026) — set this up first.

**Cloud masking**: Use the S2 cloud probability collection or QA60 band to filter/composite cloud-free pixels; build a median composite over a growing-season date range per AOI. Nepal's monsoon (Jun–Sep, overlapping the rice/kharif season) brings heavy persistent cloud cover across the whole country, including the Terai — expect to lean on wider date windows, multi-year compositing, or SAR (Sentinel-1, cloud-penetrating) as a fallback/supplement for that season specifically. The winter/rabi season (wheat, lentil, mustard) is comparatively dry and cloud-free, and is the easier season to start with.

**Feature engineering** (per pixel or per field parcel):
- Raw bands: B2, B3, B4, B8, B11, B12 (blue, green, red, NIR, SWIR1, SWIR2)
- Indices: NDVI, EVI, NDWI, NDMI, SAVI
- Temporal features: multi-date composites across the growing season (e.g., monthly NDVI time series) — critical for distinguishing crops with similar spectral signatures but different phenology, and useful in Rupandehi to separate the winter rabi crops (wheat, lentil, mustard) that share the same fields in sequence across a year
- Terrain: elevation/slope/aspect from SRTM — much less critical in Rupandehi than it was in hilly Pokhara, since the Terai is flat; still cheap to include and harmless

**Labels for training**: This is the hardest part of the project. Correction to an earlier version of this doc: it's not true that Nepal has *no* per-pixel crop data — ESA WorldCereal (`ESA/WorldCereal/2021/MARKERS/v100` in the GEE Data Catalog) is a real, free, 10m-resolution, per-pixel product with global coverage including Nepal, giving active-cropland extent plus binary maize and winter/spring cereals (wheat+barley+rye) maps with confidence layers, built from Sentinel-1+Sentinel-2. What's still accurate: no single dataset gives per-pixel labels for all 7 of this app's target classes (rice, wheat, maize, sugarcane, lentil, mustard, vegetables) the way the US CDL does — WorldCereal only directly covers cropland/maize/cereals, not rice, sugarcane, lentil, mustard, or vegetables specifically. Options, roughly in order of effort:
- **ESA WorldCereal** — use directly via GEE for cropland extent + maize + cereals (wheat/barley/rye) labels; strongest lead for those classes specifically, and can bootstrap training even before any manual labeling is done.
- ICIMOD (SERVIR-HKH) has run an operational "remote sensing-supported crop area mapping" program with Nepal's Ministry of Agriculture and Livestock Department (MoALD) since 2019, producing the government's official rice/wheat area and yield estimates, with documented field data collection in Rupandehi (wheat mapping, 2024). Worth contacting ICIMOD/SERVIR-HKH directly, or checking their data portal (rds.icimod.org), to ask whether any labeled layers are shareable.
- RicePAL (Fernandez-Beltran et al., 2021, *Remote Sensing*/MDPI): a published Sentinel-2 + climate/soil rice-yield database built from Terai districts, with a 3D-CNN yield model. Code is on GitHub (rufernan/RicePAL); the underlying ground-truth labels aren't published there, but the paper's data-availability contact is worth emailing.
- A related paper, "Rice crop classification and yield estimation using multi-temporal Sentinel-2 data: a case study of Terai districts of Nepal," corroborates that this is an active, multi-group research area.
- Manual labeling: draw field polygons over high-res basemap imagery (Esri/Sentinel-2/Bing) cross-referenced with local crop calendars — still the only realistic source for rice, sugarcane, lentil, mustard, and vegetables specifically. This is considerably more tractable in Rupandehi than it was in Pokhara, since Terai fields are large and visually distinct rather than small indistinct hillside terraces.
- Recommendation: pull WorldCereal into the pipeline now for cropland/maize/cereals (cheap, immediate improvement over synthetic labels for those classes), pursue the ICIMOD/RicePAL contacts in parallel, and hand-label the remaining classes (rice, sugarcane, lentil, mustard, vegetables) that WorldCereal doesn't cover.

## 4. ML Pipeline

1. Sample labeled pixels from the manually-labeled Rupandehi polygons (or other label source) across diverse regions/years, extract the feature stack above via GEE.
2. Train/test split with spatial blocking (avoid spatially adjacent pixels leaking between train/test).
3. Baseline model: Random Forest; compare against XGBoost/LightGBM. Class imbalance handling (rice and wheat likely dominate) via class weights or stratified sampling.
4. Evaluate with confusion matrix, per-class F1, overall accuracy, and kappa — standard in remote-sensing crop classification literature.
5. Hyperparameter tuning (grid/random search or Optuna).
6. Export final model (joblib/pickle) + feature list + class label mapping for the backend to load.
7. (Stretch goal, phase 2) CNN/U-Net on image patches for pixel-wise segmentation if classical approach plateaus — needs more labeled data and GPU compute.

## 5. Backend API (FastAPI)

Key endpoints:
- `POST /aoi` — accept AOI geometry (GeoJSON) + date range, kick off GEE image fetch + feature extraction job.
- `GET /aoi/{id}/status` — job status (for async/long-running AOI processing).
- `POST /classify/{aoi_id}` — run trained model on extracted features, return classified raster + per-class area stats.
- `GET /results/{aoi_id}` — retrieve classification GeoJSON/PNG overlay + summary stats.
- `GET /export/{aoi_id}` — generate downloadable report (PDF summary + GeoTIFF + CSV of stats).
- `GET /crops` — list of supported crop classes for current region/model version.

## 6. Frontend (Next.js)

- Map view (Mapbox GL/Leaflet) with draw-AOI tool (polygon/rectangle) and location search.
- Date range picker for the growing season/composite window.
- "Classify" action → polls job status → renders classified raster as a map overlay with a crop-class legend.
- Sidebar dashboard: per-class area (hectares/acres), bar/pie chart breakdown, confidence/accuracy indicator if available.
- Multi-region support: saved AOI list, ability to compare regions or track the same AOI over time.
- Export button: download PDF report, GeoTIFF, or CSV.

## 7. Suggested Repo Structure

```
crop-classification/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/ (aoi.py, classify.py, export.py)
│   │   ├── gee/ (auth.py, imagery.py, features.py)
│   │   ├── ml/ (inference.py, model_registry/)
│   │   └── models/ (db schema)
│   ├── training/
│   │   ├── extract_training_data.py   # GEE sampling from labeled field polygons
│   │   ├── train_model.py             # RF/XGBoost training + eval
│   │   └── notebooks/                 # EDA, model comparison
│   └── requirements.txt
├── frontend/
│   ├── app/ (Next.js pages)
│   ├── components/ (Map, Dashboard, ExportPanel)
│   └── package.json
├── data/
│   ├── models/ (trained model artifacts)
│   └── samples/ (cached training samples)
└── README.md
```

## 8. Phased Roadmap

**Phase 0 — Setup (few days)**
Register GEE + Cloud project (select noncommercial quota tier), set up repo, scaffold FastAPI + Next.js apps, confirm GEE Python auth works end-to-end.

**Phase 1 — Data & ML prototype (1–2 weeks)**
Rupandehi pilot: pursue the ICIMOD/SERVIR-HKH and RicePAL leads for real labels in parallel with manually labeling a few hundred field polygons (rice, wheat, maize, sugarcane, lentil, mustard) against Esri/Sentinel-2 basemap imagery. Extract training samples from GEE, engineer features, train and validate RF/XGBoost baseline. Target: a working model with documented accuracy metrics.

**Phase 2 — Backend integration (1 week)**
Wrap GEE fetch + feature extraction + model inference in FastAPI endpoints. Get a single AOI end-to-end: draw region → fetch imagery → classify → return results as JSON/GeoTIFF.

**Phase 3 — Frontend dashboard (1–2 weeks)**
Build map UI, AOI drawing, results overlay, stats dashboard. Wire up to backend.

**Phase 4 — Multi-region/multi-crop expansion (1–2 weeks)**
Generalize beyond the pilot region: handle different label sources per region, expand crop class list, add AOI history/comparison.

**Phase 5 — Export & polish (1 week)**
PDF/GeoTIFF/CSV export, error handling for cloud cover/no-data periods, loading states, basic auth if needed, deployment (Vercel for frontend, Cloud Run/Render for backend).

**Phase 6 (stretch) — Deep learning upgrade**
CNN/U-Net segmentation model as an alternative/ensemble to the classical model, if time and labeled data allow.

## 9. Tech Stack Summary

| Layer | Choice |
|---|---|
| Imagery/data | Google Earth Engine (Sentinel-2 SR, + Sentinel-1 SAR for monsoon gap-filling), manual field-polygon labels for Rupandehi (plus ICIMOD/RicePAL as potential real-label sources) |
| ML | Python: scikit-learn, XGBoost, geemap/earthengine-api |
| Backend | FastAPI, Celery+Redis (async jobs), PostGIS or SQLite+GeoAlchemy |
| Frontend | Next.js, Mapbox GL/Leaflet, Recharts |
| Reports | ReportLab/WeasyPrint (PDF), rasterio (GeoTIFF) |
| Deployment | Vercel (frontend), Cloud Run or Render (backend) |

## 10. Key Risks

- **No ready-made labels for all target classes**: ESA WorldCereal now supplies free per-pixel labels for cropland/maize/cereals directly in the live training pipeline (`app/gee/worldcereal.py`), but nothing covers rice, sugarcane, lentil, mustard, or vegetables — manual labeling (or securing real data from ICIMOD/RicePAL) for those remaining classes is still required and is the main bottleneck to a defensible accuracy number.
- **Field size vs. 10m pixels**: much less of a concern in Rupandehi than it was in Pokhara — Terai fields are typically large enough for clean Sentinel-2 sampling, though field boundaries should still be drawn a little inside the visible edge to avoid mixed pixels at boundaries.
- **Monsoon cloud cover**: the rice/kharif season (roughly Jun–Nov) overlaps peak monsoon nationwide, including the Terai. A Sentinel-1 SAR composite (VV/VH) is now included in the feature stack (`app/gee/imagery.py:get_sentinel1_composite`) as a cloud-independent fallback signal, though the winter/rabi season (wheat, lentil, mustard) remains the easier starting point.
- **Multi-season complexity**: the same plot can grow a monsoon crop (rice) and a different winter crop (wheat/lentil/mustard) in the same year, so "classification" needs a defined date window per run rather than one static annual label.
- **GEE quota limits**: noncommercial tier quotas are enforced (as of April 2026) — batch/async processing needed for larger AOIs to avoid timeouts.
- **Class imbalance**: rice and wheat will likely dominate over less common classes (lentil, mustard, vegetables); needs explicit handling.
- **(Reference, if a mountainous region is revisited later)**: Pokhara Valley's terraced smallholder plots are frequently smaller than a single Sentinel-2 pixel and its hilly terrain introduces shadowing/illumination artifacts — both are why Rupandehi was chosen as the more tractable pilot.

## Next Step

The repo has been scaffolded (backend + frontend, GEE auth setup, Rupandehi placeholder labels and training scripts), and several Phase 4/5 items from the roadmap above are already built ahead of schedule: phenology (monthly NDVI) features, AOI jobs persisting to SQLite with a browsable history, held-out accuracy (confusion matrix, kappa, per-class precision/recall), a rough district-level scale check against published MoALD statistics, real ESA WorldCereal per-pixel labels merged into training for non_crop/maize/wheat, a Sentinel-1 SAR fallback for monsoon cloud gaps, and GeoTIFF export — see the root README for details on each. The critical next step is real labels for the classes WorldCereal doesn't cover: reach out to ICIMOD/SERVIR-HKH and the RicePAL authors, and in parallel start hand-digitizing field polygons over Rupandehi's Terai farmland for rice, sugarcane, lentil, mustard, and vegetables.

Sources:
- [Removing access for unregistered Cloud projects](https://groups.google.com/g/google-earthengine-announce/c/fPq4zEKdTSo)
- [Authentication and Initialization — Earth Engine](https://developers.google.com/earth-engine/guides/auth)
- [High-Resolution Mapping of Seasonal Crop Pattern Using Sentinel Imagery in Mountainous Region of Nepal](https://doi.org/10.3390/geomatics3020017) (Pokhara Valley reference study)
- [Agriculture Atlas of Nepal — SERVIR-HKH / ICIMOD](https://servir.icimod.org/science-applications/agriculture-atlas-of-nepal/)
- [Satellite imagery in rice crop mapping: Sowing the seeds for stronger food security — ICIMOD Blog](https://blog.icimod.org/regional-action/satellite-imagery-in-eo-and-git-in-rice-crop-mapping/) (ICIMOD/MoALD program, Rupandehi wheat field data collection)
- [Rice-Yield Prediction with Multi-Temporal Sentinel-2 Data and 3D CNN: A Case Study in Nepal (RicePAL)](https://www.mdpi.com/2072-4292/13/7/1391)
- [RicePAL code repository](https://github.com/rufernan/RicePAL)
