import pandas as pd
import numpy as np


def get_model_features(pipeline):
    """
    Возвращает список колонок, которые ожидает Pipeline на вход.
    Обычно это то, что сохранил SimpleImputer на этапе обучения.
    """
    #imputer хранит feature_names_in_
    if hasattr(pipeline, "named_steps") and "imputer" in pipeline.named_steps:
        imp = pipeline.named_steps["imputer"]
        if hasattr(imp, "feature_names_in_"):
            return list(imp.feature_names_in_)

    #pipeline сам хранит feature_names_in_
    if hasattr(pipeline, "feature_names_in_"):
        return list(pipeline.feature_names_in_)

    #модель может хранить feature_names_in_
    if hasattr(pipeline, "named_steps") and "model" in pipeline.named_steps:
        model = pipeline.named_steps["model"]
        if hasattr(model, "feature_names_in_"):
            return list(model.feature_names_in_)

    raise RuntimeError(
        "Model does not expose feature_names_in_. "
        "Retrain model using pandas DataFrame input or save feature list separately."
    )


def build_X_for_model(df, feature_names):
    """
    Формируем X:
    - берём только smart_*_raw
    - NA -> NaN
    - приводим к числам
    - добавляем недостающие фичи (NaN)
    - оставляем только feature_names и в нужном порядке
    """
    raw_cols = [c for c in df.columns if c.startswith("smart_") and c.endswith("_raw")]
    X = df[raw_cols].copy()

    X = X.replace("NA", np.nan)
    X = X.apply(pd.to_numeric, errors="coerce")

    for c in feature_names:
        if c not in X.columns:
            X[c] = np.nan

    # строгий порядок и строгий набор
    X = X[feature_names]
    return X


def predict_from_csv(pipeline, csv_path):
    df = pd.read_csv(csv_path, na_values=["NA"])

    feature_names = get_model_features(pipeline)
    X = build_X_for_model(df, feature_names)

    pred = pipeline.predict(X)
    proba = pipeline.predict_proba(X)

    return df, pred, proba