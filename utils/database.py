"""
SQLite database layer for the crawler.

Uses WAL mode so readers (search) don't block writers (crawler).
Three tables:
  - crawl_jobs: tracks each crawl operation's config and status
  - pages: stores every crawled page with its content/words
  - word_index: inverted index mapping words → pages (for fast search)
"""

import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "crawler.db")

# One lock for schema init; after that SQLite handles concurrency via WAL
_init_lock = threading.Lock()
_initialized = False


def get_connection():
    """
    Return a new SQLite connection configured for concurrent access.
    Each thread should call this to get its own connection (sqlite3 rule).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row          # dict-like rows
    conn.execute("PRAGMA journal_mode=WAL")  # allow concurrent reads
    conn.execute("PRAGMA busy_timeout=5000") # wait up to 5s if locked
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn):
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id          TEXT PRIMARY KEY,
                origin      TEXT NOT NULL,
                max_depth   INTEGER NOT NULL,
                hit_rate    REAL NOT NULL DEFAULT 10.0,
                max_queue   INTEGER NOT NULL DEFAULT 10000,
                max_urls    INTEGER NOT NULL DEFAULT 1000,
                status      TEXT NOT NULL DEFAULT 'running',
                pages_crawled INTEGER NOT NULL DEFAULT 0,
                queue_size  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                error       TEXT
            );

            CREATE TABLE IF NOT EXISTS pages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT NOT NULL,
                origin_url  TEXT NOT NULL,
                crawl_id    TEXT NOT NULL,
                depth       INTEGER NOT NULL,
                title       TEXT,
                word_count  INTEGER NOT NULL DEFAULT 0,
                crawled_at  TEXT NOT NULL,
                FOREIGN KEY (crawl_id) REFERENCES crawl_jobs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
            CREATE INDEX IF NOT EXISTS idx_pages_crawl ON pages(crawl_id);

            CREATE TABLE IF NOT EXISTS word_index (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                word        TEXT NOT NULL,
                url         TEXT NOT NULL,
                origin_url  TEXT NOT NULL,
                crawl_id    TEXT NOT NULL,
                depth       INTEGER NOT NULL,
                frequency   INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_word ON word_index(word);
            CREATE INDEX IF NOT EXISTS idx_word_prefix ON word_index(word COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS crawl_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                crawl_id    TEXT NOT NULL,
                message     TEXT NOT NULL,
                level       TEXT NOT NULL DEFAULT 'info',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (crawl_id) REFERENCES crawl_jobs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_logs_crawl ON crawl_logs(crawl_id);
        """)
        _initialized = True


def reset_db():
    """Delete the database file and reset state. Used for testing."""
    global _initialized
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    _initialized = False
