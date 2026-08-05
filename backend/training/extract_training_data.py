"""Extract Sentinel-2 + terrain feature vectors at labeled Rupandehi field
locations, for offline model comparison (see train_model.py).

Usage:
    python training/extract_training_data.py \
        --labels training/labels/rupandehi_crops.geojson \
        --start 2023-11-01 --end 2024-03-31 \
        --out data/samples/rupandehi_training_samples.csv

The date range should match one crop season at a time -- Rupandehi has a
monsoon-season rice crop and a separate winter (rabi) wheat/lentil/mustard
season -- since the same plot can carry different crops across seasons. See
the project plan's crop calendar notes.
"""
import argparse
import json

import ee
import pandas as pd

from app.gee.auth import init_earth_engine
from app.gee.features import CLASS_PROPERTY, build_feature_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True, help="Path to labeled GeoJSON FeatureCollection")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--scale", type=int, default=10, help="Sample scale in meters")
    args = parser.parse_args()

    init_earth_engine()

    with open(args.labels) as f:
        labels_geojson = json.load(f)
    labels_fc = ee.FeatureCollection(labels_geojson)

    geometry = labels_fc.geometry().bounds().buffer(500)
    # Same feature stack used live (composite + phenology bands) -- see
    # app/gee/features.py:build_feature_image -- so a model trained on this
    # CSV uses the identical inputs the live classifier would build.
    feature_image, feature_bands = build_feature_image(geometry, args.start, args.end)

    sampled = feature_image.select(feature_bands).sampleRegions(
        collection=labels_fc,
        properties=[CLASS_PROPERTY],
        scale=args.scale,
        geometries=False,
        tileScale=4,
    )

    features = sampled.getInfo()["features"]
    rows = [f["properties"] for f in features]
    df = pd.DataFrame(rows)

    if df.empty:
        raise SystemExit(
            "No samples extracted -- check that the label polygons overlap "
            "cloud-free Sentinel-2 coverage for the given date range."
        )

    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} labeled samples to {args.out}")
    print(df[CLASS_PROPERTY].value_counts())


if __name__ == "__main__":
    main()
