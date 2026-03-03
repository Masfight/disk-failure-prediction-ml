import os
import sys
import tempfile
import joblib

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.predictor import predict_from_csv
from web.config import MODEL_PATH


def predict_from_file(file_storage):
    # сохраняем загруженный CSV во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp_path = tmp.name
        file_storage.save(tmp_path)

    try:
        pipeline = joblib.load(MODEL_PATH)
        df, pred, proba = predict_from_csv(pipeline, tmp_path)

        df = df.reset_index(drop=True)

        results = []
        for i in range(len(df)):
            serial = str(df.iloc[i]["serial_number"]) if "serial_number" in df.columns else "NA"
            model  = str(df.iloc[i]["model"]) if "model" in df.columns else "NA"

            # proba может быть None, если в пайплайне нет predict_proba
            if proba is not None:
                probs = {
                    "low": float(proba[i][0]),
                    "medium": float(proba[i][1]),
                    "high": float(proba[i][2]),
                }
            else:
                probs = None

            results.append(
                {
                    "row": i + 1,
                    "serial": serial,
                    "model": model,
                    "predicted_class": int(pred[i]),
                    "probabilities": probs,
                }
            )

        return results

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass