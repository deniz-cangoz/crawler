"""
Utilities for exporting the inverted index into the assignment's raw storage file.

Expected line format:
    word url origin depth frequency
"""

import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "data", "storage")
STORAGE_PATH = os.path.join(STORAGE_DIR, "p.data")


def ensure_storage_file():
    """Create the raw storage directory/file if missing."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(STORAGE_PATH):
        with open(STORAGE_PATH, "w", encoding="utf-8"):
            pass
    return STORAGE_PATH


def sync_storage_file(conn=None):
    """
    Rewrite data/storage/p.data from the current word_index table.

    Accepts an optional open DB connection so callers already inside a transaction
    can avoid opening a second connection.
    """
    ensure_storage_file()

    close_conn = False
    if conn is None:
        from utils.database import get_connection

        conn = get_connection()
        close_conn = True

    try:
        rows = conn.execute(
            """SELECT word, url, origin_url, depth, frequency
               FROM word_index
               ORDER BY word COLLATE NOCASE ASC, url ASC, origin_url ASC, depth ASC"""
        ).fetchall()

        with open(STORAGE_PATH, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(
                    f"{row['word']} {row['url']} {row['origin_url']} "
                    f"{row['depth']} {row['frequency']}\n"
                )
    finally:
        if close_conn:
            conn.close()

    return STORAGE_PATH
