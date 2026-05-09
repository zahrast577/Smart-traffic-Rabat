import sqlite3
import os

DB_PATH = os.path.expanduser("~/smart_traffic/sumo/traffic.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS traffic_data (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            time_s    REAL,
            camera    TEXT,
            vehicles  INTEGER,
            speed_kmh REAL,
            occupancy REAL,
            congested INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            camera     TEXT,
            time_s     REAL,
            predicted  INTEGER,
            confidence REAL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("Base de données initialisée.")

def insert_record(time_s, camera, vehicles, speed_kmh, occupancy, congested):
    conn = get_conn()
    conn.execute("""
        INSERT INTO traffic_data (time_s, camera, vehicles, speed_kmh, occupancy, congested)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (time_s, camera, vehicles, speed_kmh, occupancy, int(congested)))
    conn.commit()
    conn.close()

def insert_prediction(camera, time_s, predicted, confidence):
    conn = get_conn()
    conn.execute("""
        INSERT INTO predictions (camera, time_s, predicted, confidence)
        VALUES (?, ?, ?, ?)
    """, (camera, time_s, predicted, confidence))
    conn.commit()
    conn.close()

def get_latest(limit=100):
    conn = get_conn()
    rows = conn.execute("""
        SELECT time_s, camera, vehicles, speed_kmh, occupancy, congested
        FROM traffic_data
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

def get_summary():
    conn = get_conn()
    rows = conn.execute("""
        SELECT camera,
               SUM(vehicles)       as total,
               AVG(speed_kmh)      as avg_speed,
               AVG(congested)*100  as congestion_pct
        FROM traffic_data
        GROUP BY camera
        ORDER BY total DESC
    """).fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
