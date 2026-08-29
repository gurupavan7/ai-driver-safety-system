from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.analytics import (
    get_all_telemetry,
    get_current_status,
    get_dashboard_payload,
    get_recent_events,
    get_risk_summary,
)
from app.video_analyzer import SUPPORTED_EXTENSIONS, analyze_video


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


app = FastAPI(
    title="AI Driver Safety API",
    description="Backend API for the AI Driver Safety & Accident Prevention System",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "AI Driver Safety API is running",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-driver-safety-api",
    }


@app.get("/status")
def status():
    return get_current_status()


@app.get("/risk")
def risk():
    return get_risk_summary()


@app.get("/events")
def events(
    limit: int = Query(default=20, ge=1, le=500),
):
    return {
        "events": get_recent_events(limit=limit),
    }


@app.get("/analytics")
def analytics(
    limit: int = Query(default=300, ge=1, le=5000),
):
    return get_dashboard_payload(limit=limit)


@app.get("/history")
def history(
    limit: int = Query(default=300, ge=1, le=5000),
):
    rows = get_all_telemetry(limit=limit)
    rows = list(reversed(rows))

    return {
        "history": rows,
        "count": len(rows),
    }


@app.post("/video/analyze")
def analyze_uploaded_video(
    file: UploadFile = File(...),
):
    original_name = Path(file.filename or "video.mp4").name
    extension = Path(original_name).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {supported}",
        )

    unique_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / unique_name

    try:
        with destination.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        if destination.stat().st_size > MAX_UPLOAD_SIZE:
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=413,
                detail="Video is larger than the 500 MB upload limit.",
            )

        result = analyze_video(destination)
        result["video"]["original_file_name"] = original_name
        return result

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {exc}",
        ) from exc

    finally:
        try:
            file.file.close()
        except Exception:
            pass

        # Remove uploaded source after analysis.
        destination.unlink(missing_ok=True)
