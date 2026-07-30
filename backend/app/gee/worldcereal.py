"""ESA WorldCereal integration: pulls real per-pixel cropland/maize/cereals
labels from ESA/WorldCereal/2021/MODELS/v100 in the GEE Data Catalog, to
supplement the hand-placed placeholder training polygons.

Coverage note: WorldCereal only classifies three of this app's eight crop
classes -- temporarycrops (a catch-all "is this actively cropped land"
layer, used here for the non_crop class), maize, and wintercereals (which
WorldCereal defines as wheat, barley, and rye combined; used here as a proxy
for wheat, the dominant winter cereal in Rupandehi). It says nothing about
rice, sugarcane, lentil, mustard, or vegetables specifically, so it is a
partial supplement to the placeholder labels, not a full replacement -- see
project_plan.md section 3 for the fuller data-availability picture.

Each WorldCereal product image carries a `classification` band (0 or 100)
and a `confidence` band (0-100); only pixels at or above
CONFIDENCE_THRESHOLD are used as label points here, since a low-confidence
WorldCereal pixel is not a reliable ground-truth label.
"""
import ee

from app.config import get_settings

WORLDCEREAL_MODELS = "ESA/WorldCereal/2021/MODELS/v100"
CONFIDENCE_THRESHOLD = 70


def _product_mosaic(product: str) -> ee.Image:
    """Global mosaic of one WorldCereal product, merging all its
    agro-ecological-zone tiles into a single image (matches the basic usage
    pattern shown in the dataset's own GEE Data Catalog example)."""
    return (
        ee.ImageCollection(WORLDCEREAL_MODELS)
        .filter(ee.Filter.eq("product", product))
        .mosaic()
    )


def _confident_classification(product: str) -> ee.Image:
    img = _product_mosaic(product)
    return img.select("classification").updateMask(
        img.select("confidence").gte(CONFIDENCE_THRESHOLD)
    )


def sample_worldcereal_points(
    geometry: ee.Geometry, num_points: int = 40, seed: int = 42
) -> ee.FeatureCollection:
    """Stratified sample of WorldCereal-derived label points within geometry.

    Maps WorldCereal's binary products onto this app's crop_class scheme:
      temporarycrops == 0   -> non_crop
      maize == 100           -> maize
      wintercereals == 100   -> wheat

    Uses stratifiedSample rather than a plain random sample so all three
    represented classes get points, instead of whichever class covers the
    most area within `geometry` dominating the sample.
    """
    settings = get_settings()
    class_index = {name: i for i, name in enumerate(settings.crop_classes)}
    non_crop_id = class_index.get("non_crop", 0)
    maize_id = class_index.get("maize", non_crop_id)
    wheat_id = class_index.get("wheat", non_crop_id)

    temporarycrops = _confident_classification("temporarycrops")
    maize = _confident_classification("maize")
    wintercereals = _confident_classification("wintercereals")

    # Base label is non_crop wherever temporarycrops says inactive/no
    # cropland, then overwritten with the more specific maize/wheat label
    # wherever those season-specific products say active -- an actively
    # grown field should win over the coarser cropland-only layer.
    label_image = (
        ee.Image(non_crop_id)
        .where(temporarycrops.eq(0), non_crop_id)
        .where(maize.eq(100), maize_id)
        .where(wintercereals.eq(100), wheat_id)
        .rename("crop_class")
        .updateMask(
            temporarycrops.mask().Or(maize.mask()).Or(wintercereals.mask())
        )
    )

    points = label_image.stratifiedSample(
        numPoints=num_points,
        classBand="crop_class",
        region=geometry,
        scale=10,
        seed=seed,
        geometries=True,
    )
    return points.map(lambda f: f.set("source", "ESA_WorldCereal"))


def build_combined_training_labels(
    manual_labels: ee.FeatureCollection,
    geometry: ee.Geometry,
    include_worldcereal: bool = True,
    worldcereal_points: int = 40,
) -> ee.FeatureCollection:
    """Manual placeholder polygons plus, by default, WorldCereal-derived
    points sampled over the same extent, merged into one FeatureCollection
    ready for features.sample_training_features.

    If the WorldCereal sample comes back empty (e.g. an AOI/date combination
    with no confident WorldCereal coverage), merging in zero extra points is
    harmless -- training just proceeds on the manual labels alone, same as
    before this feature existed.
    """
    if not include_worldcereal:
        return manual_labels
    worldcereal_labels = sample_worldcereal_points(geometry, num_points=worldcereal_points)
    return manual_labels.merge(worldcereal_labels)
