import sqlite3
from pathlib import Path
from datetime import datetime
from app.paths import DATA_DIR

DB_PATH = DATA_DIR / "driver_safety.db"


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_telemetry_table():
    """
    Create the continuous telemetry table if it does not already exist.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ear REAL NOT NULL,
            mar REAL NOT NULL,
            pitch REAL NOT NULL,
            yaw REAL NOT NULL,
            head_direction TEXT NOT NULL,
            phone_detected INTEGER NOT NULL,
            seatbelt_detected INTEGER NOT NULL,
            drowsy INTEGER NOT NULL,
            yawning INTEGER NOT NULL,
            distracted INTEGER NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


def log_telemetry(
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
    risk_level,
):
    """
    Save one telemetry sample.
    """
    timestamp = datetime.now().isoformat(timespec="milliseconds")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO telemetry (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            float(ear),
            float(mar),
            float(pitch),
            float(yaw),
            str(head_direction),
            int(bool(phone_detected)),
            int(bool(seatbelt_detected)),
            int(bool(drowsy)),
            int(bool(yawning)),
            int(bool(distracted)),
            int(risk_score),
            str(risk_level),
        ),
    )

    connection.commit()
    connection.close()


def get_recent_telemetry(limit=100):
    connection = get_connection()
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT *
        FROM telemetry
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_telemetry_count():
    connection = get_connection()
    cursor = connection.cursor()

    row = cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM telemetry
        """
    ).fetchone()

    connection.close()

    return int(row["count"])


if __name__ == "__main__":
    init_telemetry_table()

    print("✅ Telemetry table ready.")
    print(f"Database: {DB_PATH}")
    print(f"Current telemetry rows: {get_telemetry_count()}")
