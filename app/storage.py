import sqlite3

from app.paths import DATA_DIR

DB_PATH = DATA_DIR / "driver_safety.db"


def init_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            details TEXT
        )
        """
    )

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


if __name__ == "__main__":
    init_storage()

    print(f"Storage initialized: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )

    print("Tables:", [row[0] for row in cursor.fetchall()])

    connection.close()
