"""
CrawlerJob — a threaded BFS web crawler.

Each crawl runs as a daemon thread so it doesn't block shutdown.

Key design choices (matching assignment requirements):
  - BFS via queue.Queue  →  depth tracking is natural
  - Bounded queue        →  back pressure when frontier grows too large
  - Rate limiter         →  sleep between requests to control load
  - Max-URL cap          →  hard stop so large crawls don't run forever
  - Visited-URL set      →  never crawl the same page twice
  - SQLite storage       →  search can query while indexing continues (WAL)
  - Pause / stop events  →  graceful control from outside the thread
  - Queue persistence    →  resume after interruption
"""

import threading
import queue
import time
import ssl
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from utils.html_parser import parse_html
from utils.database import get_connection


class CrawlerJob(threading.Thread):
    """
    A single crawl operation that runs in its own thread.

    Usage:
        job = CrawlerJob(crawl_id, origin, max_depth, ...)
        job.start()        # non-blocking
        job.pause()        # pause mid-crawl
        job.resume()       # continue
        job.stop()         # graceful stop
    """

    def __init__(self, crawl_id, origin, max_depth,
                 hit_rate=10.0, max_queue=10000, max_urls=1000,
                 resume_queue=None):
        super().__init__(daemon=True)
        self.crawl_id = crawl_id
        self.origin = origin
        self.max_depth = max_depth
        self.hit_rate = hit_rate
        self.max_queue = max_queue
        self.max_urls = max_urls

        # Thread-safe frontier — bounded for back pressure
        self.url_queue = queue.Queue(maxsize=max_queue)
        self.visited = set()
        self.pages_crawled = 0
        self.status = "running"
        self.error = None

        # Control events
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # start un-paused

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_interval = 1.0 / hit_rate if hit_rate > 0 else 0

        # SSL context — try verified first, fallback to unverified
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx_unverified = ssl._create_unverified_context()

        # If resuming, seed from saved queue; otherwise seed from origin
        if resume_queue:
            for url, depth in resume_queue:
                self.url_queue.put((url, depth))
        else:
            self.url_queue.put((origin, 0))

    # ---- public control methods ----

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused so thread can exit
        self.status = "stopped"

    def pause(self):
        self._pause_event.clear()
        self.status = "paused"

    def resume(self):
        self._pause_event.set()
        self.status = "running"

    def get_state(self):
        """Snapshot of current state for the API."""
        return {
            "crawl_id": self.crawl_id,
            "origin": self.origin,
            "status": self.status,
            "pages_crawled": self.pages_crawled,
            "queue_size": self.url_queue.qsize(),
            "max_depth": self.max_depth,
            "hit_rate": self.hit_rate,
            "max_queue": self.max_queue,
            "max_urls": self.max_urls,
            "error": self.error,
        }

    # ---- main loop ----

    def run(self):
        """BFS crawl loop running in this thread."""
        conn = get_connection()
        is_resume = bool(self.visited) or self.url_queue.qsize() > 1
        if is_resume:
            self._log(conn, f"Crawl resumed: {self.origin} (depth={self.max_depth})")
        else:
            self._log(conn, f"Crawl started: {self.origin} (depth={self.max_depth})")

        # Load already-visited URLs for this crawl (for resume support)
        rows = conn.execute(
            "SELECT url FROM pages WHERE crawl_id = ?", (self.crawl_id,)
        ).fetchall()
        for row in rows:
            self.visited.add(row["url"])
        # Sync counter with DB (important for resume — don't start from 0)
        self.pages_crawled = len(self.visited)

        try:
            while not self._stop_event.is_set():
                # Respect pause
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                # Check URL cap
                if self.pages_crawled >= self.max_urls:
                    self._log(conn, f"Reached max URLs limit ({self.max_urls})")
                    break

                # Get next URL from queue (timeout lets us check stop flag)
                try:
                    url, depth = self.url_queue.get(timeout=1)
                except queue.Empty:
                    # Queue exhausted → crawl complete
                    break

                # Skip if already visited or beyond depth
                if url in self.visited or depth > self.max_depth:
                    continue

                # Rate limit
                self._rate_limit()

                # Crawl the page
                self._crawl_url(conn, url, depth)

            # Finished
            if self.status != "stopped":
                self.status = "completed"
            self._log(conn, f"Crawl finished. Pages: {self.pages_crawled}")

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self._log(conn, f"Crawl error: {e}", level="error")

        finally:
            # Persist final state
            self._save_queue(conn)
            self._update_job_status(conn)
            conn.close()

    # ---- internal methods ----

    def _crawl_url(self, conn, url, depth):
        """Fetch a single URL, parse it, store results, enqueue new links."""
        self.visited.add(url)

        # Fetch HTML
        html = self._fetch(url)
        if html is None:
            return

        # Parse
        title, text, links, word_counts = parse_html(html, url)

        # Store page
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO pages (url, origin_url, crawl_id, depth, title, word_count, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (url, self.origin, self.crawl_id, depth, title, sum(word_counts.values()), now),
        )

        # Store word index (batch insert for performance)
        if word_counts:
            conn.executemany(
                """INSERT INTO word_index (word, url, origin_url, crawl_id, depth, frequency)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (word, url, self.origin, self.crawl_id, depth, freq)
                    for word, freq in word_counts.items()
                ],
            )

        conn.commit()
        self.pages_crawled += 1
        self._update_job_status(conn)

        # Enqueue discovered links at depth + 1
        if depth < self.max_depth:
            enqueued = 0
            for link in links:
                if link not in self.visited and self.pages_crawled + self.url_queue.qsize() < self.max_urls * 2:
                    try:
                        self.url_queue.put_nowait((link, depth + 1))
                        enqueued += 1
                    except queue.Full:
                        self._log(conn, f"Queue full ({self.max_queue}), skipping new URLs", level="warn")
                        break

        self._log(conn, f"[d={depth}] {url} — {len(word_counts)} unique words, {len(links)} links")

    def _fetch(self, url):
        """
        Fetch URL content using stdlib urllib.
        Returns HTML string or None on failure.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; CrawlerBot/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            # Try with verified SSL first
            try:
                resp = urllib.request.urlopen(req, context=self._ssl_ctx, timeout=10)
            except ssl.SSLError:
                resp = urllib.request.urlopen(req, context=self._ssl_ctx_unverified, timeout=10)

            # Only process HTML responses
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            # Read with size limit (10 MB)
            data = resp.read(10 * 1024 * 1024)
            charset = resp.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")

        except Exception:
            return None

    def _rate_limit(self):
        """Sleep if needed to respect hit_rate. Uses short sleeps so stop/pause respond quickly."""
        if self._request_interval <= 0:
            return
        elapsed = time.time() - self._last_request_time
        remaining = self._request_interval - elapsed
        # Sleep in 0.1s chunks so we can respond to stop/pause quickly
        while remaining > 0 and not self._stop_event.is_set() and self._pause_event.is_set():
            time.sleep(min(remaining, 0.1))
            remaining -= 0.1
        self._last_request_time = time.time()

    def _log(self, conn, message, level="info"):
        """Write a log entry to the database."""
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO crawl_logs (crawl_id, message, level, created_at) VALUES (?, ?, ?, ?)",
            (self.crawl_id, message, level, now),
        )
        conn.commit()

    def _update_job_status(self, conn):
        """Persist current job state to DB."""
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE crawl_jobs
               SET status = ?, pages_crawled = ?, queue_size = ?, updated_at = ?, error = ?
               WHERE id = ?""",
            (self.status, self.pages_crawled, self.url_queue.qsize(), now, self.error, self.crawl_id),
        )
        conn.commit()

    def _save_queue(self, conn):
        """
        Persist remaining queue to DB so the crawl can be resumed.
        Stored as JSON in the crawl_jobs table's error field (reusing for simplicity),
        but we'll use a dedicated approach: save as a log entry with level='queue'.
        """
        remaining = []
        while not self.url_queue.empty():
            try:
                url, depth = self.url_queue.get_nowait()
                remaining.append([url, depth])
            except queue.Empty:
                break

        if remaining:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO crawl_logs (crawl_id, message, level, created_at) VALUES (?, ?, ?, ?)",
                (self.crawl_id, json.dumps(remaining), "queue", now),
            )
            conn.commit()
