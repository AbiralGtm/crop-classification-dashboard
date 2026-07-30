"""Sampling helpers for building a training FeatureCollection and running
server-side classification in GEE.

Design note: rather than training an sklearn model locally and trying to
serialize it into GEE, inference here uses GEE's native
ee.Classifier.smileRandomForest, trained directly on a FeatureCollection of
labeled points and applied to the composite image server-side. This avoids
exporting per-pixel arrays over the wire and scales to arbitrary AOI sizes.
The offline sklearn/XGBoost workflow in training/train_model.py is for
feature/model comparison and computing rigorous accuracy metrics (confusion
matrix, per-class F1, kappa) that GEE's classifier accuracy() does not surface
as conveniently; the winning feature recipe is mirrored into this module.
"""
import ee

from app.config import get_settings
from app.gee.imagery import (
    SAR_BANDS,
    get_monthly_ndvi_image,
    get_sentinel1_composite,
    get_sentinel2_composite,
)
from app.gee.worldcereal import build_combined_training_labels

# Base (non-temporal) feature bands: raw reflectance + indices + terrain from
# a single averaged composite. The full feature list used for a given
# request also appends the Sentinel-1 SAR bands and monthly NDVI bands
# (ndvi_m0, ndvi_m1, ...) -- see build_feature_image() -- since the number
# of months depends on the request's date range and can't be a fixed
# module-level constant.
FEATURE_BANDS = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "NDVI", "NDWI", "NDMI", "EVI", "SAVI",
    "elevation", "slope", "aspect",
]
CLASS_PROPERTY = "crop_class"  # integer label property on training features
N_TREES = 200


def build_feature_image(
    geometry: ee.Geometry, start_date: str, end_date: str
) -> tuple[ee.Image, list[str]]:
    """The full per-pixel feature stack for a request: the averaged Sentinel-2
    composite (spectral bands + indices + terrain), the Sentinel-1 SAR
    composite (VV/VH, cloud-independent), and per-month NDVI phenology bands.

    Returns the image together with the exact band-name list to `.select()`,
    since that list is date-range-dependent (see imagery.month_count). Every
    caller within a single request -- training sampling and AOI
    classification alike -- must use the band list returned here rather than
    the static FEATURE_BANDS constant, so they agree on inputs.
    """
    composite = get_sentinel2_composite(geometry, start_date, end_date)
    sar = get_sentinel1_composite(geometry, start_date, end_date)
    monthly_ndvi, monthly_band_names = get_monthly_ndvi_image(geometry, start_date, end_date)
    full_image = composite.addBands(sar).addBands(monthly_ndvi)
    full_bands = FEATURE_BANDS + SAR_BANDS + monthly_band_names
    return full_image, full_bands


def load_training_points(labels_asset_or_geojson) -> ee.FeatureCollection:
    """Load a FeatureCollection of labeled points/polygons.

    `labels_asset_or_geojson` can be a GEE asset id string (e.g.
    'projects/your-project/assets/pokhara_crop_labels') or a local GeoJSON
    FeatureCollection dict (converted with ee.FeatureCollection(geojson)).
    Each feature must carry an integer `crop_class` property matching the
    index into settings.crop_classes.
    """
    if isinstance(labels_asset_or_geojson, str):
        return ee.FeatureCollection(labels_asset_or_geojson)
    return ee.FeatureCollection(labels_asset_or_geojson)


def sample_training_features(
    image: ee.Image,
    labeled_regions: ee.FeatureCollection,
    feature_bands: list[str],
    scale: int = 10,
) -> ee.FeatureCollection:
    """Sample feature-image band values at labeled polygon/point locations."""
    return image.select(feature_bands).sampleRegions(
        collection=labeled_regions,
        properties=[CLASS_PROPERTY],
        scale=scale,
        geometries=False,
    )


def train_rf_classifier(
    training_features: ee.FeatureCollection, feature_bands: list[str]
) -> ee.Classifier:
    classifier = ee.Classifier.smileRandomForest(numberOfTrees=N_TREES).train(
        features=training_features,
        classProperty=CLASS_PROPERTY,
        inputProperties=feature_bands,
    )
    return classifier


def classify_aoi(
    geometry: ee.Geometry,
    start_date: str,
    end_date: str,
    labeled_regions: ee.FeatureCollection,
    include_worldcereal: bool = True,
) -> tuple[ee.Image, ee.Classifier, ee.FeatureCollection, list[str]]:
    """Build the feature image for the AOI/date range and classify it.

    `labeled_regions` is the raw labeled polygon/point FeatureCollection (only
    carrying class properties, no band values yet). It must be sampled against
    a feature image before training -- the classifier needs actual
    B2/B3/.../slope/phenology values per labeled feature, not just the class
    label.

    Training features are sampled from a feature image built over the
    labeled regions' own extent, not the AOI being classified: the AOI a user
    draws can be anywhere and any size, while the (currently placeholder)
    label polygons sit at fixed coordinates. Sampling against an AOI-clipped
    image would return nothing whenever the AOI doesn't happen to cover those
    exact spots, which is what caused "No valid training data were found"
    earlier.

    When include_worldcereal is True (the default), real per-pixel points
    sampled from ESA WorldCereal (see app/gee/worldcereal.py) are merged in
    alongside the manual labeled_regions before sampling, for the three
    classes WorldCereal covers (non_crop, maize, wheat). This never removes
    or overrides the manual labels, only adds to them.

    Also returns the sampled `training_features` and the `feature_bands` list
    used, so the caller can separately run `evaluate_classifier` on them for
    a held-out accuracy estimate without re-sampling or re-deriving band names.
    """
    training_extent = labeled_regions.geometry().bounds().buffer(200)
    combined_labels = build_combined_training_labels(
        labeled_regions, training_extent, include_worldcereal=include_worldcereal
    )
    training_image, feature_bands = build_feature_image(training_extent, start_date, end_date)
    training_features = sample_training_features(training_image, combined_labels, feature_bands)
    classifier = train_rf_classifier(training_features, feature_bands)

    aoi_image, aoi_feature_bands = build_feature_image(geometry, start_date, end_date)
    # aoi_feature_bands is always equal to feature_bands here: both are
    # derived purely from start_date/end_date (see imagery.month_count), so
    # the two calls agree on band names regardless of the differing geometry.
    classified = aoi_image.select(aoi_feature_bands).classify(classifier)
    return classified, classifier, training_features, feature_bands


def evaluate_classifier(
    training_features: ee.FeatureCollection,
    feature_bands: list[str],
    test_fraction: float = 0.25,
    seed: int = 42,
) -> ee.Dictionary:
    """Train on a random subset of labeled points, evaluate on the rest.

    This is a *separate, informational-only* classifier -- the classifier
    used to actually produce the AOI map (`classify_aoi`) always trains on
    every labeled point, so this evaluation split never shrinks the
    already-scarce training data used for the live result. All values in the
    returned dictionary are still `ee.Number`/`ee.List` objects; the caller
    should `.getInfo()` it (see `ml/inference.py`).

    With only a handful of labeled points per class, expect this to be
    degenerate -- e.g. a class with zero points in the test split. That's
    expected and should be surfaced to the user as "not enough data yet",
    not treated as a real accuracy number.
    """
    settings = get_settings()
    class_order = list(range(len(settings.crop_classes)))

    with_random = training_features.randomColumn("split_random", seed)
    train_set = with_random.filter(ee.Filter.gte("split_random", test_fraction))
    test_set = with_random.filter(ee.Filter.lt("split_random", test_fraction))

    eval_classifier = train_rf_classifier(train_set, feature_bands)
    test_classified = test_set.classify(eval_classifier)
    error_matrix = test_classified.errorMatrix(CLASS_PROPERTY, "classification", class_order)

    return ee.Dictionary(
        {
            "train_count": train_set.size(),
            "test_count": test_set.size(),
            "overall_accuracy": error_matrix.accuracy(),
            "kappa": error_matrix.kappa(),
            "producers_accuracy": error_matrix.producersAccuracy(),
            "consumers_accuracy": error_matrix.consumersAccuracy(),
            "class_order": class_order,
        }
    )


def class_area_stats(
    classified: ee.Image, geometry: ee.Geometry, scale: int = 10
) -> ee.Dictionary:
    """Per-class pixel counts within the AOI, convertible to hectares by the
    caller (pixel_count * scale^2 / 10000)."""
    settings = get_settings()
    area_img = ee.Image.pixelArea().addBands(classified.rename("class"))
    stats = area_img.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
        geometry=geometry,
        scale=scale,
        maxPixels=1e10,
    )
    return stats
