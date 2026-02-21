import os
import sys
from flask import Flask, render_template, request, redirect, url_for, request

LAST_RESULTS = None
LAST_REPORT_PATH = None
LAST_ERROR = None

def _get_prob(r, key: str) -> float:
    probs = r.get("probabilities")
    if not probs:
        return 0.0
    return float(probs.get(key, 0.0))

def sort_results(items, mode: str):
    items = list(items or [])

    if mode == "risk_desc":
        # Высокий риск сверху: 2 -> 1 -> 0
        return sorted(items, key=lambda r: (r.get("predicted_class", -1), _get_prob(r, "high")), reverse=True)

    if mode == "risk_asc":
        # Низкий риск сверху: 0 -> 1 -> 2
        return sorted(items, key=lambda r: (r.get("predicted_class", 999), _get_prob(r, "high")))

    if mode == "high_prob_desc":
        # По вероятности high по убыванию
        return sorted(items, key=lambda r: _get_prob(r, "high"), reverse=True)

    # по умолчанию без сортировки
    return items

def calc_risk_counts(items):
    counts = {"low": 0, "medium": 0, "high": 0}
    for r in items or []:
        cls = r.get("predicted_class")
        if cls == 0:
            counts["low"] += 1
        elif cls == 1:
            counts["medium"] += 1
        elif cls == 2:
            counts["high"] += 1
    return counts

# добавляем корень проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from web.pipeline import predict_from_file
from web.reports import save_report

app = Flask(__name__)

@app.route("/")
def index():
    global LAST_RESULTS, LAST_REPORT_PATH, LAST_ERROR

    sort_mode = request.args.get("sort", "risk_desc")  # режим по умолчанию

    results_sorted = sort_results(LAST_RESULTS, sort_mode)
    counts = calc_risk_counts(results_sorted)

    return render_template(
        "index.html",
        results=results_sorted,
        report_path=LAST_REPORT_PATH,
        error=LAST_ERROR,
        sort_mode=sort_mode,
        counts=counts,
        total=len(results_sorted or []),
    )

@app.route("/predict", methods=["POST"])
def predict():
    global LAST_RESULTS, LAST_REPORT_PATH, LAST_ERROR

    file = request.files.get("file")
    if not file:
        LAST_ERROR = "Файл не выбран"
        return redirect(url_for("index"))

    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        LAST_ERROR = "Неверный формат файла. Требуется CSV."
        return redirect(url_for("index"))

    LAST_ERROR = None
    LAST_RESULTS = predict_from_file(file)
    LAST_REPORT_PATH = save_report({"items": LAST_RESULTS})

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)