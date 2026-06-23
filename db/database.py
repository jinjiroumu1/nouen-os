import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "nouen_os.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS farm_diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            weather TEXT,
            crop TEXT,
            work_done TEXT,
            observation TEXT,
            question TEXT,
            hypothesis TEXT,
            advice TEXT,
            source_type TEXT DEFAULT 'souhatsuchi',
            color TEXT DEFAULT 'pink',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS cultivation_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            crop TEXT NOT NULL,
            sowing_date TEXT,
            planting_date TEXT,
            harvest_period TEXT,
            companion_plants TEXT,
            required_materials TEXT,
            source_type TEXT DEFAULT 'souhatsuchi',
            color TEXT DEFAULT 'pink',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT NOT NULL,
            vegetable TEXT,
            ingredients TEXT,
            season TEXT,
            notes TEXT,
            source_type TEXT DEFAULT 'souhatsuchi',
            color TEXT DEFAULT 'pink',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT,
            related_topics TEXT,
            source_type TEXT DEFAULT 'souhatsuchi',
            color TEXT DEFAULT 'pink',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS network_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            type TEXT,
            source_type TEXT,
            color TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS network_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_node TEXT NOT NULL,
            to_node TEXT NOT NULL,
            relationship TEXT,
            weight INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()
