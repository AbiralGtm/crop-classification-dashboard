"""Sentinel-2 imagery fetch, cloud masking, spectral indices, and terrain features.

Built around GEE's COPERNICUS/S2_SR_HARMONIZED collection. Terrain (slope/aspect)
is included as a feature for generality -- it mattered a lot for an earlier
Pokhara Valley pilot (hilly/terraced terrain, where slope affects both crop
suitability and illumination-driven spectral distortion) and costs little to
keep even though the current Rupandehi (Terai) pilot is flat.
"""
from datetime import date

import ee

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_PROB_COLLECTION = "COPERNICUS/S2_CLOUD_PROBABILITY"
S1_COLLECTION = "COPERNICUS/S1_GRD"
SRTM = "USGS/SRTMGL1_003"

# Sentinel-1 bands used as SAR features.
SAR_BANDS = ["VV", "VH"]

# Sentinel-2 bands used as raw features.
BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
BAND_NAMES = ["blue", "green", "red", "nir", "swir1", "swir2"]

CLOUD_PROB_THRESHOLD = 40  # % cloud probability above which a pixel is masked


def _mask_clouds(image: ee.Image) -> ee.Image:
    cloud_prob = ee.Image(image.get("cloud_mask")).select("probability")
    is_clear = cloud_prob.lt(CLOUD_PROB_THRESHOLD)
    return image.updateMask(is_clear)


def _add_indices(image: ee.Image) -> ee.Image:
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    ndmi = image.normalizedDifference(["B8", "B11"]).rename("NDMI")
    evi = image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {
            "NIR": image.select("B8"),
            "RED": image.select("B4"),
            "BLUE": image.select("B2"),
        },
    ).rename("EVI")
    savi = image.expression(
        "((NIR - RED) / (NIR + RED + 0.5)) * 1.5",
        {"NIR": image.select("B8"), "RED": image.select("B4")},
    ).rename("SAVI")
    return image.addBands([ndvi, ndwi, ndmi, evi, savi])


def _add_terrain(image: ee.Image, geometry: ee.Geometry) -> ee.Image:
    dem = ee.Image(SRTM).clip(geometry)
    terrain = ee.Terrain.products(dem)  # adds elevation, slope, aspect, hillshade
    return image.addBands(terrain.select(["elevation", "slope", "aspect"]))


def get_sentinel2_composite(
    geometry: ee.Geometry, start_date: str, end_date: str
) -> ee.Image:
    """Cloud-masked median composite over the date range, with indices + terrain.

    For the Jun-Sep monsoon window (overlapping the summer rice/millet season),
    this can still have data gaps from persistent cloud cover even after
    masking. build_feature_image (app/gee/features.py) now also adds a
    Sentinel-1 SAR composite (see get_sentinel1_composite below) alongside
    this one, since radar sees through cloud cover and gives the classifier
    a fallback signal for those gaps.
    """
    s2 = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
    )
    cloud_prob = (
        ee.ImageCollection(S2_CLOUD_PROB_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
    )

    joined = ee.Join.saveFirst("cloud_mask").apply(
        primary=s2,
        secondary=cloud_prob,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    masked = ee.ImageCollection(joined).map(_mask_clouds)

    composite = masked.select(BANDS).median().clip(geometry)
    composite = _add_indices(composite)
    composite = _add_terrain(composite, geometry)
    return composite


def get_sentinel1_composite(
    geometry: ee.Geometry, start_date: str, end_date: str
) -> ee.Image:
    """Median VV/VH backscatter composite from Sentinel-1 GRD, in decibels.

    Sentinel-1 is radar, not optical, so it sees through cloud cover
    entirely. Adding its two bands to the feature stack gives the classifier
    a usable signal even during the monsoon (roughly Jun-Nov) when the
    Sentinel-2 composite in get_sentinel2_composite can have gaps or
    all-masked pixels from persistent cloud cover -- this was flagged as an
    unimplemented risk in project_plan.md section 10 and is now wired in.

    Filtered to IW (interferometric wide swath) mode with both VV and VH
    polarisations, since that is the mode Sentinel-1 uses over most land
    areas including Nepal. If a date range/AOI genuinely has no Sentinel-1
    scenes, the median() below returns a fully masked image rather than
    raising, so callers still get an image with the right band names.
    """
    s1 = (
        ee.ImageCollection(S1_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(SAR_BANDS)
    )
    return s1.median().clip(geometry)


def get_monthly_ndvi_series(
    geometry: ee.Geometry, start_date: str, end_date: str
) -> ee.ImageCollection:
    """Monthly NDVI composites across the date range, for phenology-based features.

    Crops with similar single-date spectral signatures (e.g. wheat vs. lentil)
    are often separable by *when* they green up and senesce, which matters in
    Rupandehi since a monsoon crop (rice) and a winter crop (wheat/lentil/
    mustard) can occupy the same plot in sequence within a single year.
    """
    start = ee.Date(start_date)
    end = ee.Date(end_date)
    n_months = end.difference(start, "month").round()

    def _monthly(i):
        month_start = start.advance(i, "month")
        month_end = month_start.advance(1, "month")
        img = (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(month_start, month_end)
            .select(BANDS)
            .median()
        )
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return ndvi.set("system:time_start", month_start.millis())

    months = ee.List.sequence(0, n_months.subtract(1))
    return ee.ImageCollection(months.map(_monthly))


def month_count(start_date: str, end_date: str) -> int:
    """Number of whole calendar months between two YYYY-MM-DD dates.

    Computed client-side (plain Python) rather than via a GEE round trip so
    callers can know the phenology feature band names (`ndvi_m0`, `ndvi_m1`,
    ...) up front, before making any Earth Engine calls -- both the training
    sampling and the AOI classification need to agree on the exact same band
    list for a given request.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(months, 1)


def get_monthly_ndvi_image(
    geometry: ee.Geometry, start_date: str, end_date: str
) -> tuple[ee.Image, list[str]]:
    """Stack per-month NDVI composites into one multi-band image with
    deterministic band names (`ndvi_m0`, `ndvi_m1`, ...), for use as
    classifier features alongside the single averaged composite.

    This is what actually makes phenology usable as a *feature*: a wheat
    field looks like bare soil early in the season and green later, while
    rice on a different calendar looks nothing like that -- a single
    averaged composite (get_sentinel2_composite) blurs that trajectory away,
    but a per-month NDVI value for each labeled point lets the classifier
    see the shape of the curve, not just its average.
    """
    band_names = [f"ndvi_m{i}" for i in range(month_count(start_date, end_date))]
    start = ee.Date(start_date)

    monthly_images = []
    for i, name in enumerate(band_names):
        month_start = start.advance(i, "month")
        month_end = month_start.advance(1, "month")
        img = (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(month_start, month_end)
            .select(BANDS)
            .median()
        )
        ndvi = img.normalizedDifference(["B8", "B4"]).rename(name)
        monthly_images.append(ndvi)

    return ee.Image.cat(monthly_images), band_names
