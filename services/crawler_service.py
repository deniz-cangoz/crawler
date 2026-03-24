"""
Crawler service — manages crawler job lifecycle.

Responsibilities:
  - Create new crawl jobs (spawn threads)
  - Track active crawlers in memory
  - Pause / resume / stop crawlers
  - Resume from DB after restart
  - Provide status info for the API
"""

import threading
import json
from datetime import datetime, timezone

from utils.database import get_connection
from utils.crawler_job import CrawlerJob
from utils.storage_export import sync_storage_file

# In-memory registry of active crawler threads
_active_crawlers = {}   # crawl_id → CrawlerJob
_lock = threading.Lock()


def create_crawler(origin, max_depth, hit_rate=10.0, max_queue=10000, max_urls=1000):
    """
    Create and start a new crawl job.
    Returns the crawl_id for tracking.
    """
    now = datetime.now(timezone.utc)
    crawl_id = f"{int(now.timestamp())}_{threading.current_thread().ident}"

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO crawl_jobs (id, origin, max_depth, hit_rate, max_queue, max_urls,
                                       status, pages_crawled, queue_size, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'running', 0, 1, ?, ?)""",
            (crawl_id, origin, max_depth, hit_rate, max_queue, max_urls,
             now.isoformat(), now.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    job = CrawlerJob(
        crawl_id=crawl_id,
        origin=origin,
        max_depth=max_depth,
        hit_rate=hit_rate,
        max_queue=max_queue,
        max_urls=max_urls,
    )

    with _lock:
        _active_crawlers[crawl_id] = job

    job.start()
    return {"crawl_id": crawl_id, "status": "running"}


def get_crawler_status(crawl_id):
    """Get live status from the thread if active, or from DB if finished."""
    with _lock:
        job = _active_crawlers.get(crawl_id)

    if job and job.is_alive():
        return job.get_state()

    # Not active — read from DB
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM crawl_jobs WHERE id = ?", (crawl_id,)).fetchone()
        if not row:
            return {"error": f"Crawler {crawl_id} not found"}
        return dict(row)
    finally:
        conn.close()


def get_crawler_logs(crawl_id, limit=100):
    """Get recent log entries for a crawl job."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT message, level, created_at FROM crawl_logs
               WHERE crawl_id = ? AND level != 'queue'
               ORDER BY id DESC LIMIT ?""",
            (crawl_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_crawlers():
    """List all crawl jobs (active and finished)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM crawl_jobs ORDER BY created_at DESC"
        ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            # Override with live status if active
            with _lock:
                job = _active_crawlers.get(data["id"])
            if job and job.is_alive():
                data.update(job.get_state())
            results.append(data)
        return results
    finally:
        conn.close()


def stop_crawler(crawl_id):
    """Stop an active crawler."""
    with _lock:
        job = _active_crawlers.get(crawl_id)
    if not job or not job.is_alive():
        # Update DB status anyway (thread may have died)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE crawl_jobs SET status = 'stopped', updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), crawl_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "stopped", "crawl_id": crawl_id}
    job.stop()
    return {"status": "stopped", "crawl_id": crawl_id}


def pause_crawler(crawl_id):
    """Pause an active crawler."""
    with _lock:
        job = _active_crawlers.get(crawl_id)
    if not job or not job.is_alive():
        return {"error": "Crawler is not active"}
    job.pause()
    return {"status": "paused", "crawl_id": crawl_id}


def resume_crawler(crawl_id):
    """Resume a paused (or stopped) crawler."""
    with _lock:
        job = _active_crawlers.get(crawl_id)

    # If the thread is alive but paused, just un-pause
    if job and job.is_alive():
        job.resume()
        return {"status": "running", "crawl_id": crawl_id}

    # Otherwise try to resume from DB (restart the thread with saved queue)
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM crawl_jobs WHERE id = ?", (crawl_id,)).fetchone()
        if not row:
            return {"error": f"Crawler {crawl_id} not found"}

        # Load saved queue
        queue_row = conn.execute(
            """SELECT message FROM crawl_logs
               WHERE crawl_id = ? AND level = 'queue'
               ORDER BY id DESC LIMIT 1""",
            (crawl_id,),
        ).fetchone()

        resume_queue = None
        if queue_row:
            resume_queue = [tuple(item) for item in json.loads(queue_row["message"])]

        if not resume_queue:
            # No queue saved — crawl was likely complete or queue was empty at stop time
            return {"error": "No URLs left to resume — the crawl was complete or queue was empty when stopped"}

        new_job = CrawlerJob(
            crawl_id=crawl_id,
            origin=row["origin"],
            max_depth=row["max_depth"],
            hit_rate=row["hit_rate"],
            max_queue=row["max_queue"],
            max_urls=row["max_urls"],
            resume_queue=resume_queue,
        )

        with _lock:
            _active_crawlers[crawl_id] = new_job

        # Update status in DB
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE crawl_jobs SET status = 'running', updated_at = ? WHERE id = ?",
            (now, crawl_id),
        )
        conn.commit()

        new_job.start()
        return {"status": "running", "crawl_id": crawl_id}
    finally:
        conn.close()


def clear_all_data():
    """Clear all crawl data. Stops active crawlers first."""
    with _lock:
        for cid, job in _active_crawlers.items():
            if job.is_alive():
                job.stop()
        _active_crawlers.clear()

    conn = get_connection()
    try:
        conn.executescript("""
            DELETE FROM word_index;
            DELETE FROM pages;
            DELETE FROM crawl_logs;
            DELETE FROM crawl_jobs;
        """)
        conn.commit()
        sync_storage_file(conn)
        return {"status": "cleared"}
    finally:
        conn.close()


def get_statistics():
    """Get overall crawler statistics."""
    conn = get_connection()
    try:
        stats = {}
        stats["total_jobs"] = conn.execute("SELECT COUNT(*) FROM crawl_jobs").fetchone()[0]
        stats["total_pages"] = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        stats["total_words"] = conn.execute("SELECT COUNT(DISTINCT word) FROM word_index").fetchone()[0]
        stats["active_crawlers"] = sum(
            1 for j in _active_crawlers.values() if j.is_alive()
        )
        return stats
    finally:
        conn.close()
