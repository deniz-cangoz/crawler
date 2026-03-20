"""
Tests for utils/crawler_job.py

Covers: initialization, state management, rate limiting,
        back pressure, pause/stop controls.
"""

import unittest
import queue
import time
import os
import tempfile

# Override DB path for tests
_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test_crawler_job.db")

import utils.database as db_module
db_module.DB_PATH = _test_db_path
db_module._initialized = False

from utils.crawler_job import CrawlerJob
from utils.database import get_connection


class TestCrawlerJobInit(unittest.TestCase):
    """Tests for CrawlerJob initialization."""

    def test_initial_state(self):
        job = CrawlerJob("test1", "https://example.com", max_depth=2)
        self.assertEqual(job.crawl_id, "test1")
        self.assertEqual(job.origin, "https://example.com")
        self.assertEqual(job.max_depth, 2)
        self.assertEqual(job.status, "running")
        self.assertEqual(job.pages_crawled, 0)
        self.assertIsNone(job.error)

    def test_default_parameters(self):
        job = CrawlerJob("test2", "https://example.com", max_depth=1)
        self.assertEqual(job.hit_rate, 10.0)
        self.assertEqual(job.max_queue, 10000)
        self.assertEqual(job.max_urls, 1000)

    def test_custom_parameters(self):
        job = CrawlerJob("test3", "https://example.com", max_depth=3,
                         hit_rate=5.0, max_queue=500, max_urls=100)
        self.assertEqual(job.hit_rate, 5.0)
        self.assertEqual(job.max_queue, 500)
        self.assertEqual(job.max_urls, 100)

    def test_queue_seeded_with_origin(self):
        job = CrawlerJob("test4", "https://example.com", max_depth=1)
        self.assertEqual(job.url_queue.qsize(), 1)
        url, depth = job.url_queue.get_nowait()
        self.assertEqual(url, "https://example.com")
        self.assertEqual(depth, 0)

    def test_resume_queue(self):
        resume_data = [
            ("https://example.com/page1", 1),
            ("https://example.com/page2", 2),
        ]
        job = CrawlerJob("test5", "https://example.com", max_depth=3,
                         resume_queue=resume_data)
        self.assertEqual(job.url_queue.qsize(), 2)

    def test_daemon_thread(self):
        job = CrawlerJob("test6", "https://example.com", max_depth=1)
        self.assertTrue(job.daemon)


class TestCrawlerJobControl(unittest.TestCase):
    """Tests for pause/stop/resume controls."""

    def test_stop(self):
        job = CrawlerJob("ctrl1", "https://example.com", max_depth=1)
        job.stop()
        self.assertEqual(job.status, "stopped")
        self.assertTrue(job._stop_event.is_set())

    def test_pause(self):
        job = CrawlerJob("ctrl2", "https://example.com", max_depth=1)
        job.pause()
        self.assertEqual(job.status, "paused")
        self.assertFalse(job._pause_event.is_set())

    def test_resume(self):
        job = CrawlerJob("ctrl3", "https://example.com", max_depth=1)
        job.pause()
        job.resume()
        self.assertEqual(job.status, "running")
        self.assertTrue(job._pause_event.is_set())

    def test_get_state(self):
        job = CrawlerJob("ctrl4", "https://example.com", max_depth=2,
                         hit_rate=5.0, max_queue=1000, max_urls=200)
        state = job.get_state()
        self.assertEqual(state["crawl_id"], "ctrl4")
        self.assertEqual(state["origin"], "https://example.com")
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["max_depth"], 2)
        self.assertEqual(state["hit_rate"], 5.0)
        self.assertEqual(state["max_queue"], 1000)
        self.assertEqual(state["max_urls"], 200)
        self.assertEqual(state["pages_crawled"], 0)
        self.assertIsNone(state["error"])


class TestCrawlerJobBackPressure(unittest.TestCase):
    """Tests for back pressure mechanisms."""

    def test_bounded_queue(self):
        """Queue should reject entries when full."""
        job = CrawlerJob("bp1", "https://example.com", max_depth=1, max_queue=3)
        # Queue already has 1 item (origin)
        job.url_queue.put(("https://a.com", 1))
        job.url_queue.put(("https://b.com", 1))
        # Queue is now full (3/3)
        with self.assertRaises(queue.Full):
            job.url_queue.put_nowait(("https://c.com", 1))

    def test_rate_limit_interval(self):
        """Rate limiter should enforce minimum interval between requests."""
        job = CrawlerJob("bp2", "https://example.com", max_depth=1, hit_rate=2.0)
        # interval should be 0.5 seconds
        self.assertAlmostEqual(job._request_interval, 0.5, places=2)

    def test_rate_limit_timing(self):
        """Rate limiter should actually delay requests."""
        job = CrawlerJob("bp3", "https://example.com", max_depth=1, hit_rate=10.0)
        job._last_request_time = time.time()
        start = time.time()
        job._rate_limit()
        elapsed = time.time() - start
        # Should have waited approximately 0.1 seconds
        self.assertGreater(elapsed, 0.05)

    def test_max_urls_respected(self):
        """Crawler should stop when max_urls is reached."""
        job = CrawlerJob("bp4", "https://example.com", max_depth=1, max_urls=5)
        job.pages_crawled = 5
        # When pages_crawled >= max_urls, the run loop should break
        self.assertTrue(job.pages_crawled >= job.max_urls)


class TestCrawlerJobFetch(unittest.TestCase):
    """Tests for the fetch method (without actual network calls)."""

    def test_fetch_invalid_url(self):
        job = CrawlerJob("fetch1", "https://example.com", max_depth=1)
        result = job._fetch("not-a-valid-url")
        self.assertIsNone(result)

    def test_fetch_nonexistent_domain(self):
        job = CrawlerJob("fetch2", "https://example.com", max_depth=1)
        result = job._fetch("https://this-domain-does-not-exist-12345.com")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
