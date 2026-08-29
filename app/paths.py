import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PERSISTENT_ROOT = Path(
    os.getenv("PERSISTENT_ROOT", BASE_DIR)
).resolve()

DATA_DIR = PERSISTENT_ROOT / "data"
LOGS_DIR = PERSISTENT_ROOT / "logs"
REPORTS_DIR = PERSISTENT_ROOT / "reports"
UPLOADS_DIR = PERSISTENT_ROOT / "uploads"
ANALYZED_VIDEOS_DIR = PERSISTENT_ROOT / "analyzed_videos"

for directory in (
    DATA_DIR,
    LOGS_DIR,
    REPORTS_DIR,
    UPLOADS_DIR,
    ANALYZED_VIDEOS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
