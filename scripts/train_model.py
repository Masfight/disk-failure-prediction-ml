import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import json
from datetime import datetime
import joblib
import os
import time

DATA_PATH = "data/datasets/harddrive.csv"
MODEL_PATH = "models/random_forest_hdd.joblib"

def save_report(y_test, y_pred, macro_f1, train_time, report_dir="reports"):
    os.makedirs(report_dir, exist_ok=True)

    # 1. Classification report (text)
    report_text = classification_report(y_test, y_pred)

    report_path = os.path.join(report_dir, "classification_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 2. Confusion matrix (CSV)
    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(cm)
    cm_path = os.path.join(report_dir, "confusion_matrix.csv")
    cm_df.to_csv(cm_path, index=False)

    # 3. Метрики в JSON
    metrics = {
        "macro_f1": float(macro_f1),
        "train_time_seconds": float(train_time),
        "timestamp": datetime.now().isoformat()
    }

    metrics_path = os.path.join(report_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)

    print(f"\nReport saved to {report_dir}/")


def load_data_chunked(path, chunksize=200_000, usecols=None):
    chunks = []
    total = 0
    for chunk in pd.read_csv(path, chunksize=chunksize, usecols=usecols):
        total += len(chunk)
        #print(f"Loaded rows: {total:,}", flush=True)
        chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True)


def build_target(df):
    df['date'] = pd.to_datetime(df['date'])

    failure_dates = (
        df.loc[df['failure'] == 1, ['serial_number', 'date']]
        .groupby('serial_number', sort=False)['date']
        .min()
    )

    df['failure_date'] = df['serial_number'].map(failure_dates)
    days = (df['failure_date'] - df['date']).dt.days
    df['days_to_failure'] = days.fillna(9999)

    df['risk_class'] = 0
    df.loc[df['days_to_failure'] <= 30, 'risk_class'] = 1
    df.loc[df['days_to_failure'] <= 7, 'risk_class'] = 2

    return df


def select_features(df):
    feature_cols = [c for c in df.columns if c.startswith("smart_") and c.endswith("_raw")]

    # Удаляем признаки, где все значения NA
    non_empty = [c for c in feature_cols if not df[c].isna().all()]

    dropped = sorted(set(feature_cols) - set(non_empty))
    if dropped:
        print(f"Dropped empty features: {dropped}", flush=True)

    X = df[non_empty]
    y = df['risk_class']
    return X, y


def train_model(X, y):
    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestClassifier(
            n_estimators=500,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1,
            verbose=2
        ))
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    start_time = time.time()

    pipeline.fit(X_train, y_train)

    train_time = time.time() - start_time

    y_pred = pipeline.predict(X_test)

    print("\nClassification report:")
    print(classification_report(y_test, y_pred))

    print("\nConfusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    macro_f1 = f1_score(y_test, y_pred, average='macro')
    print(f"\nMacro F1: {macro_f1:.4f}")
    print(f"Training time: {train_time:.1f}s")

    save_report(y_test, y_pred, macro_f1, train_time)
    return pipeline


def save_model(model, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    print(f"\nModel saved to {path}")


if __name__ == "__main__":
    t0 = time.time()

    # Чтобы ускорить чтение — можно ограничить колонки:
    # date, serial_number, failure + smart_*_raw
    df = load_data_chunked(DATA_PATH, chunksize=200_000)
    print(f"[load] done in {time.time()-t0:.1f}s", flush=True)

    t = time.time()
    df = build_target(df)
    print(f"[target] done in {time.time()-t:.1f}s", flush=True)

    X, y = select_features(df)

    t = time.time()
    model = train_model(X, y)
    print(f"[train] done in {time.time()-t:.1f}s", flush=True)

    save_model(model, MODEL_PATH)
