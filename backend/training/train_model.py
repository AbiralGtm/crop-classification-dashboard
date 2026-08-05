"""Offline model comparison: Random Forest vs. XGBoost on extracted features.

This is the experimentation workflow referenced in the project plan --
Random Forest and XGBoost are compared here with full sklearn evaluation
tooling (confusion matrix, per-class F1, Cohen's kappa) to decide on a
feature set and get a documented accuracy number. The winning feature recipe
is what actually gets served, via GEE's native ee.Classifier.smileRandomForest
running server-side on each AOI request -- see app/gee/features.py's module
docstring for why.

Feature columns are inferred from the CSV (everything except the class
column) rather than imported from a fixed constant, since the phenology
bands (ndvi_m0, ndvi_m1, ...) vary in count depending on the date range used
when the CSV was extracted -- see app/gee/features.py:build_feature_image.

Usage:
    python training/train_model.py --data data/samples/rupandehi_training_samples.csv \
        --out data/models/rupandehi_rf.joblib
"""
import argparse

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, cohen_kappa_score, confusion_matrix
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.config import get_settings
from app.gee.features import CLASS_PROPERTY


def evaluate(name: str, model, X_test, y_test, class_names) -> None:
    preds = model.predict(X_test)
    kappa = cohen_kappa_score(y_test, preds)
    print(f"\n=== {name} ===")
    print(f"Cohen's kappa: {kappa:.3f}")
    print(
        classification_report(
            y_test, preds, labels=sorted(set(y_test)),
            target_names=[class_names[i] for i in sorted(set(y_test))],
            zero_division=0,
        )
    )
    print("Confusion matrix (rows=true, cols=predicted):")
    print(confusion_matrix(y_test, preds, labels=sorted(set(y_test))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="CSV from extract_training_data.py")
    parser.add_argument("--out", required=True, help="Path to save the winning model (.joblib)")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    settings = get_settings()
    df = pd.read_csv(args.data)

    feature_bands = [c for c in df.columns if c != CLASS_PROPERTY]
    X = df[feature_bands]
    y = df[CLASS_PROPERTY]

    # NOTE: a plain random split is used here for simplicity. Once samples carry
    # spatial coordinates, prefer a spatial block split (group by field/plot id
    # or a coarse grid cell) so train/test pixels from the same field don't leak
    # across the split -- see the project plan's ML pipeline notes.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y
    )

    class_weights = "balanced"  # counter rice/maize dominance over rarer classes

    rf = RandomForestClassifier(
        n_estimators=300, max_depth=None, class_weight=class_weights, random_state=args.seed
    )
    rf.fit(X_train, y_train)
    evaluate("Random Forest", rf, X_test, y_test, settings.crop_classes)

    sample_weight = y_train.map(y_train.value_counts(normalize=True).rpow(-1))
    xgb = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1,
        eval_metric="mlogloss", random_state=args.seed,
    )
    xgb.fit(X_train, y_train, sample_weight=sample_weight)
    evaluate("XGBoost", xgb, X_test, y_test, settings.crop_classes)

    # Pick Random Forest as the default to save, since it mirrors the
    # GEE-native ee.Classifier.smileRandomForest used for live inference --
    # swap this if XGBoost clearly wins on your data.
    joblib.dump(
        {"model": rf, "features": feature_bands, "classes": settings.crop_classes}, args.out
    )
    print(f"\nSaved Random Forest model to {args.out}")


if __name__ == "__main__":
    main()
