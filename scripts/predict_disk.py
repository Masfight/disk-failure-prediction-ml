import pandas as pd
import numpy as np
import joblib

MODEL_PATH = "models/random_forest_hdd.joblib"
CSV_PATH = "data/datasets/smartctl_2026-02-18.csv"

def get_model_features(pipeline):
    if hasattr(pipeline, "feature_names_in_"):
        return list(pipeline.feature_names_in_)
    if hasattr(pipeline.named_steps["model"], "feature_names_in_"):
        return list(pipeline.named_steps["model"].feature_names_in_)
    raise RuntimeError("Model does not expose feature_names_in_. Retrain with pandas DataFrame input.")

def build_X_for_model(df, feature_names):
    # только raw-колонки из входного файла
    raw_cols = [c for c in df.columns if c.startswith("smart_") and c.endswith("_raw")]
    X = df[raw_cols].copy()

    # привести NA/строки в NaN и числа
    X = X.replace("NA", np.nan)
    X = X.apply(pd.to_numeric, errors="coerce")

    # добавить недостающие признаки
    for c in feature_names:
        if c not in X.columns:
            X[c] = np.nan

    # убрать лишние признаки которые не заполнены были у всех дисков и которые мы исключали из модели
    X = X[feature_names]
    return X

def main():
    print("Loading model...")
    pipeline = joblib.load(MODEL_PATH)

    print("Loading disk data...")
    df = pd.read_csv(CSV_PATH, na_values=["NA"])

    feature_names = get_model_features(pipeline)
    X = build_X_for_model(df, feature_names)

    print("Running prediction...")
    pred = pipeline.predict(X)[0]
    proba = pipeline.predict_proba(X)[0]

    print(f"\nPredicted class: {pred}")
    print(f"Class probabilities: {proba}")

if __name__ == "__main__":
    main()