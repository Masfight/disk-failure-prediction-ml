import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "models", "random_forest_hdd.joblib")
REPORTS_FOLDER = os.path.join(BASE_DIR, "..", "reports")