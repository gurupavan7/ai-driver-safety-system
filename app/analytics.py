import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from app.paths import DATA_DIR

DB_PATH = DATA_DIR / "driver_safety.db"


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _safe_json_load(value):
    if not value:
        return {}

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def get_all_events(limit=None):
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT id, timestamp, event_type, risk_score, details
        FROM events
        ORDER BY id DESC
    """

    params = ()

    if limit is not None:
        query += " LIMIT ?"
        params = (int(limit),)

    rows = cursor.execute(query, params).fetchall()
    connection.close()

    events = []

    for row in rows:
        events.append(
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "risk_score": row["risk_score"],
                "details": _safe_json_load(row["details"]),
            }
        )

    return events


def get_all_telemetry(limit=None):
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            id,
            timestamp,
            ear,
            mar,
            pitch,
            yaw,
            head_direction,
            phone_detected,
            seatbelt_detected,
            drowsy,
            yawning,
            distracted,
            risk_score,
            risk_level
        FROM telemetry
        ORDER BY id DESC
    """

    params = ()

    if limit is not None:
        query += " LIMIT ?"
        params = (int(limit),)

    rows = cursor.execute(query, params).fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_event_counts():
    events = get_all_events()
    counts = Counter(event["event_type"] for event in events)

    supported_types = [
        "DROWSINESS",
        "YAWN",
        "DISTRACTION",
        "PHONE",
        "NO_SEATBELT",
    ]

    return {
        event_type: counts.get(event_type, 0)
        for event_type in supported_types
    }


def get_risk_summary():
    connection = get_connection()
    cursor = connection.cursor()

    row = cursor.execute(
        """
        SELECT
            COUNT(*) AS samples,
            COALESCE(AVG(risk_score), 0) AS average_risk,
            COALESCE(MAX(risk_score), 0) AS max_risk,
            COALESCE(MIN(risk_score), 0) AS min_risk
        FROM telemetry
        """
    ).fetchone()

    connection.close()

    average_risk = round(float(row["average_risk"]), 2)
    max_risk = int(row["max_risk"])
    min_risk = int(row["min_risk"])

    if max_risk >= 70:
        peak_level = "HIGH"
    elif max_risk >= 35:
        peak_level = "MEDIUM"
    else:
        peak_level = "LOW"

    return {
        "samples": int(row["samples"]),
        "average_risk": average_risk,
        "max_risk": max_risk,
        "min_risk": min_risk,
        "peak_risk_level": peak_level,
    }


def get_recent_events(limit=10):
    return get_all_events(limit=limit)


def get_risk_timeline(limit=300):
    telemetry = list(reversed(get_all_telemetry(limit=limit)))

    return [
        {
            "timestamp": row["timestamp"],
            "risk_score": row["risk_score"],
            "risk_level": row["risk_level"],
        }
        for row in telemetry
    ]


def get_fatigue_timeline(limit=300):
    telemetry = list(reversed(get_all_telemetry(limit=limit)))

    return [
        {
            "timestamp": row["timestamp"],
            "ear": row["ear"],
            "mar": row["mar"],
            "drowsy": bool(row["drowsy"]),
            "yawning": bool(row["yawning"]),
        }
        for row in telemetry
    ]


def get_head_pose_timeline(limit=300):
    telemetry = list(reversed(get_all_telemetry(limit=limit)))

    return [
        {
            "timestamp": row["timestamp"],
            "pitch": row["pitch"],
            "yaw": row["yaw"],
            "head_direction": row["head_direction"],
            "distracted": bool(row["distracted"]),
        }
        for row in telemetry
    ]


def get_phone_timeline(limit=300):
    telemetry = list(reversed(get_all_telemetry(limit=limit)))

    return [
        {
            "timestamp": row["timestamp"],
            "phone_detected": bool(row["phone_detected"]),
        }
        for row in telemetry
    ]


def get_seatbelt_timeline(limit=300):
    telemetry = list(reversed(get_all_telemetry(limit=limit)))

    return [
        {
            "timestamp": row["timestamp"],
            "seatbelt_detected": bool(row["seatbelt_detected"]),
        }
        for row in telemetry
    ]


def get_current_status():
    telemetry = get_all_telemetry(limit=1)

    if not telemetry:
        return {
            "available": False,
            "message": "No telemetry available yet.",
        }

    row = telemetry[0]

    return {
        "available": True,
        "timestamp": row["timestamp"],
        "ear": row["ear"],
        "mar": row["mar"],
        "pitch": row["pitch"],
        "yaw": row["yaw"],
        "head_direction": row["head_direction"],
        "phone_detected": bool(row["phone_detected"]),
        "seatbelt_detected": bool(row["seatbelt_detected"]),
        "drowsy": bool(row["drowsy"]),
        "yawning": bool(row["yawning"]),
        "distracted": bool(row["distracted"]),
        "risk_score": row["risk_score"],
        "risk_level": row["risk_level"],
    }


def get_session_summary():
    connection = get_connection()
    cursor = connection.cursor()

    telemetry_row = cursor.execute(
        """
        SELECT
            COUNT(*) AS samples,
            MIN(timestamp) AS start_time,
            MAX(timestamp) AS end_time,
            COALESCE(AVG(risk_score), 0) AS average_risk,
            COALESCE(MAX(risk_score), 0) AS max_risk,
            SUM(CASE WHEN drowsy = 1 THEN 1 ELSE 0 END) AS drowsy_samples,
            SUM(CASE WHEN yawning = 1 THEN 1 ELSE 0 END) AS yawn_samples,
            SUM(CASE WHEN distracted = 1 THEN 1 ELSE 0 END) AS distracted_samples,
            SUM(CASE WHEN phone_detected = 1 THEN 1 ELSE 0 END) AS phone_samples,
            SUM(CASE WHEN seatbelt_detected = 0 THEN 1 ELSE 0 END) AS no_seatbelt_samples
        FROM telemetry
        """
    ).fetchone()

    connection.close()

    return {
        "samples": int(telemetry_row["samples"]),
        "start_time": telemetry_row["start_time"],
        "end_time": telemetry_row["end_time"],
        "average_risk": round(float(telemetry_row["average_risk"]), 2),
        "max_risk": int(telemetry_row["max_risk"]),
        "drowsy_samples": int(telemetry_row["drowsy_samples"] or 0),
        "yawn_samples": int(telemetry_row["yawn_samples"] or 0),
        "distracted_samples": int(telemetry_row["distracted_samples"] or 0),
        "phone_samples": int(telemetry_row["phone_samples"] or 0),
        "no_seatbelt_samples": int(telemetry_row["no_seatbelt_samples"] or 0),
    }


def get_dashboard_payload(limit=300):
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_status": get_current_status(),
        "risk_summary": get_risk_summary(),
        "event_counts": get_event_counts(),
        "session_summary": get_session_summary(),
        "recent_events": get_recent_events(limit=10),
        "charts": {
            "risk": get_risk_timeline(limit=limit),
            "fatigue": get_fatigue_timeline(limit=limit),
            "head_pose": get_head_pose_timeline(limit=limit),
            "phone": get_phone_timeline(limit=limit),
            "seatbelt": get_seatbelt_timeline(limit=limit),
        },
    }


def print_dashboard_summary():
    payload = get_dashboard_payload(limit=30)

    print("\n" + "=" * 62)
    print("AI DRIVER SAFETY - PHASE 11 ANALYTICS")
    print("=" * 62)

    risk = payload["risk_summary"]
    events = payload["event_counts"]
    session = payload["session_summary"]
    current = payload["current_status"]

    print(f"Telemetry Samples      : {risk['samples']}")
    print(f"Average Risk           : {risk['average_risk']}/100")
    print(f"Maximum Risk           : {risk['max_risk']}/100")
    print(f"Peak Risk Level        : {risk['peak_risk_level']}")
    print("-" * 62)
    print(f"Drowsiness Events      : {events['DROWSINESS']}")
    print(f"Yawn Events            : {events['YAWN']}")
    print(f"Distraction Events     : {events['DISTRACTION']}")
    print(f"Phone Events           : {events['PHONE']}")
    print(f"Seatbelt Violations    : {events['NO_SEATBELT']}")
    print("-" * 62)
    print(f"Session Start          : {session['start_time']}")
    print(f"Session End            : {session['end_time']}")
    print(f"Session Samples        : {session['samples']}")

    if current["available"]:
        print("-" * 62)
        print(f"Current Risk           : {current['risk_score']}/100 ({current['risk_level']})")
        print(f"Current Head Direction : {current['head_direction']}")
        print(f"Phone Detected         : {current['phone_detected']}")
        print(f"Seatbelt Detected      : {current['seatbelt_detected']}")

    print("=" * 62 + "\n")


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run the driver monitoring system first.")
    else:
        print_dashboard_summary()
