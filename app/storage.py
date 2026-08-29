from pathlib import Path
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

    connection.commit()
    connection.close()

if __name__ == "__main__":
    init_storage()
    print(f"Storage initialized: {DB_PATH}")