"""
Tests for services/search_service.py

Uses a temporary in-memory-like SQLite DB seeded with test data.
Covers: exact match, prefix match, multi-word queries, pagination, sorting.
"""

import unittest
import os
import tempfile
from unittest.mock import patch

# We need to override DB_PATH before importing the modules
_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test_crawler.db")


class TestSearchService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a test database with sample data."""
        # Patch DB_PATH before importing
        import utils.database as db_module
        db_module.DB_PATH = _test_db_path
        db_module._initialized = False

        from utils.database import get_connection
        conn = get_connection()

        # Insert sample word_index data
        sample_data = [
            # (word, url, origin_url, crawl_id, depth, frequency)
            ("python", "https://python.org", "https://python.org", "test1", 0, 50),
            ("python", "https://python.org/docs", "https://python.org", "test1", 1, 30),
            ("python", "https://wiki.org/python", "https://wiki.org", "test2", 0, 20),
            ("programming", "https://python.org", "https://python.org", "test1", 0, 25),
            ("programming", "https://wiki.org/coding", "https://wiki.org", "test2", 1, 15),
            ("language", "https://python.org", "https://python.org", "test1", 0, 10),
            ("web", "https://web.dev", "https://web.dev", "test3", 0, 40),
            ("web", "https://wiki.org/web", "https://wiki.org", "test2", 1, 20),
            ("crawler", "https://web.dev/crawler", "https://web.dev", "test3", 1, 35),
            ("javascript", "https://js.org", "https://js.org", "test4", 0, 45),
        ]
        conn.executemany(
            """INSERT INTO word_index (word, url, origin_url, crawl_id, depth, frequency)
               VALUES (?, ?, ?, ?, ?, ?)""",
            sample_data,
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        if os.path.exists(_test_db_path):
            os.remove(_test_db_path)

    def setUp(self):
        """Ensure search service uses patched DB."""
        import utils.database as db_module
        db_module.DB_PATH = _test_db_path

    def test_exact_match(self):
        from services.search_service import search
        result = search("python")
        self.assertGreater(result["total_results"], 0)
        urls = [r["relevant_url"] for r in result["results"]]
        self.assertIn("https://python.org", urls)

    def test_prefix_match(self):
        """'prog' should match 'programming' via prefix."""
        from services.search_service import search
        result = search("prog")
        urls = [r["relevant_url"] for r in result["results"]]
        self.assertIn("https://python.org", urls)

    def test_multi_word_query(self):
        """Multi-word query should return pages matching any word."""
        from services.search_service import search
        result = search("python web")
        self.assertGreater(result["total_results"], 0)
        # python.org should score high (matches "python")
        # web.dev should also appear (matches "web")
        urls = [r["relevant_url"] for r in result["results"]]
        self.assertIn("https://python.org", urls)
        self.assertIn("https://web.dev", urls)

    def test_multi_word_bonus(self):
        """Pages matching more query words should score higher."""
        from services.search_service import search
        result = search("python programming language")
        # python.org matches all 3 words — should be first
        self.assertEqual(result["results"][0]["relevant_url"], "https://python.org")

    def test_no_results(self):
        from services.search_service import search
        result = search("xyznonexistent")
        self.assertEqual(result["total_results"], 0)
        self.assertEqual(result["results"], [])

    def test_empty_query(self):
        from services.search_service import search
        result = search("")
        self.assertEqual(result["total_results"], 0)

    def test_pagination_limit(self):
        from services.search_service import search
        result = search("python", page_limit=1)
        self.assertLessEqual(len(result["results"]), 1)

    def test_pagination_offset(self):
        from services.search_service import search
        all_results = search("python", page_limit=100)
        offset_results = search("python", page_limit=100, page_offset=1)
        if all_results["total_results"] > 1:
            self.assertEqual(len(offset_results["results"]), len(all_results["results"]) - 1)

    def test_sort_by_depth(self):
        from services.search_service import search
        result = search("python", sort_by="depth")
        depths = [r["depth"] for r in result["results"]]
        self.assertEqual(depths, sorted(depths))

    def test_query_words_returned(self):
        from services.search_service import search
        result = search("python web")
        self.assertIn("python", result["query_words"])
        self.assertIn("web", result["query_words"])

    def test_result_triple_format(self):
        """Each result should contain the required triple fields."""
        from services.search_service import search
        result = search("python")
        for r in result["results"]:
            self.assertIn("relevant_url", r)
            self.assertIn("origin_url", r)
            self.assertIn("depth", r)

    def test_special_characters_in_query(self):
        """Query with special chars should not crash."""
        from services.search_service import search
        result = search("python!@#$%")
        # Should still find 'python' after normalization
        self.assertGreater(result["total_results"], 0)


if __name__ == "__main__":
    unittest.main()
