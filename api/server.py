from __future__ import annotations

import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.telemetry import init_telemetry_table, log_telemetry
from app.email_alerts import send_high_risk_email

from app.analytics import (
    get_all_telemetry,
    get_current_status,
    get_dashboard_payload,
    get_recent_events,
    get_risk_summary,
)
from app.paths import UPLOADS_DIR
from app.report_generator import generate_session_report, generate_video_report
from app.storage import init_storage
from app.video_analyzer import SUPPORTED_EXTENSIONS, analyze_video


MAX_UPLOAD_SIZE = 500 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Driver Safety database...")

    init_storage()
    init_telemetry_table()

    print("Driver Safety database initialized successfully.")

    yield


app = FastAPI(
    title="AI Driver Safety API",
    description="Backend API for the AI Driver Safety & Accident Prevention System",
    version="3.0.0",
    lifespan=lifespan,
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
        "version": "3.0.0",
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
def events(limit: int = Query(default=20, ge=1, le=500)):
    return {
        "events": get_recent_events(limit=limit),
    }


@app.get("/analytics")
def analytics(limit: int = Query(default=300, ge=1, le=5000)):
    return get_dashboard_payload(limit=limit)


@app.get("/history")
def history(limit: int = Query(default=300, ge=1, le=5000)):
    rows = get_all_telemetry(limit=limit)
    rows = list(reversed(rows))

    return {
        "history": rows,
        "count": len(rows),
    }


@app.post("/video/analyze")
def analyze_uploaded_video(file: UploadFile = File(...)):
    original_name = Path(file.filename or "video.mp4").name
    extension = Path(original_name).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {supported}",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOADS_DIR / unique_name

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

        destination.unlink(missing_ok=True)


@app.get("/reports/session")
def download_session_report():
    try:
        report_path = generate_session_report()

        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=report_path.name,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Session report generation failed: {exc}",
        ) from exc


@app.post("/reports/video")
def download_video_report(
    analysis: dict = Body(...),
):
    try:
        report_path = generate_video_report(analysis)

        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=report_path.name,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video report generation failed: {exc}",
        ) from exc

@app.post("/telemetry/live")
def receive_live_telemetry(payload: dict = Body(...)):
    try:
        telemetry_payload = {
            "ear": float(payload["ear"]),
            "mar": float(payload["mar"]),
            "pitch": float(payload["pitch"]),
            "yaw": float(payload["yaw"]),
            "head_direction": str(payload["head_direction"]),
            "phone_detected": bool(payload["phone_detected"]),
            "seatbelt_detected": bool(payload["seatbelt_detected"]),
            "drowsy": bool(payload["drowsy"]),
            "yawning": bool(payload["yawning"]),
            "distracted": bool(payload["distracted"]),
            "risk_score": int(payload["risk_score"]),
            "risk_level": str(payload["risk_level"]),
        }

        # Store telemetry in Railway database
        log_telemetry(**telemetry_payload)

        # Trigger email automatically when risk >= 70.
        # LOW and MEDIUM risk will not send email.
        # email_alerts.py also enforces a 5-minute cooldown.
        email_alert_status = send_high_risk_email(
            telemetry_payload
        )

        return {
            "status": "ok",
            "message": "Live telemetry received",
            "email_alert": email_alert_status,
        }

    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid telemetry payload: {exc}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store telemetry: {exc}",
        ) from exc

