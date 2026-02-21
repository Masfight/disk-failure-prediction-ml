import json
import os
from datetime import datetime
from .config import REPORTS_FOLDER


def save_report(result):
    os.makedirs(REPORTS_FOLDER, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORTS_FOLDER, f"web_report_{timestamp}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return report_path