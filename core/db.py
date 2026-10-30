from pathlib import Path
import sqlite3

def initialize_database(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    first = not db_path.exists()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS mm3_meta(key TEXT PRIMARY KEY, value TEXT)")
    con.commit()
    con.close()
    return first
