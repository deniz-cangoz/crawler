"""
Tests for utils/html_parser.py

Covers: text extraction, link extraction, word counting,
        edge cases (malformed HTML, empty pages, special tags).
"""

import unittest
from utils.html_parser import parse_html


class TestParseHtmlTextExtraction(unittest.TestCase):
    """Tests for visible text extraction."""

    def test_basic_text(self):
        html = "<html><body><p>Hello World</p></body></html>"
        title, text, links, words = parse_html(html, "https://example.com")
        self.assertIn("Hello", text)
        self.assertIn("World", text)

    def test_skips_script_tags(self):
        html = "<html><body><script>var x = 1;</script><p>Visible</p></body></html>"
        _, text, _, _ = parse_html(html, "https://example.com")
        self.assertIn("Visible", text)
        self.assertNotIn("var", text)

    def test_skips_style_tags(self):
        html = "<html><body><style>.cls { color: red; }</style><p>Content</p></body></html>"
        _, text, _, _ = parse_html(html, "https://example.com")
        self.assertIn("Content", text)
        self.assertNotIn("color", text)

    def test_skips_noscript_tags(self):
        html = "<html><body><noscript>Enable JS</noscript><p>Main</p></body></html>"
        _, text, _, _ = parse_html(html, "https://example.com")
        self.assertIn("Main", text)
        self.assertNotIn("Enable", text)

    def test_extracts_title(self):
        html = "<html><head><title>My Page</title></head><body></body></html>"
        title, _, _, _ = parse_html(html, "https://example.com")
        self.assertEqual(title, "My Page")

    def test_empty_html(self):
        title, text, links, words = parse_html("", "https://example.com")
        self.assertEqual(title, "")
        self.assertEqual(text, "")
        self.assertEqual(links, [])
        self.assertEqual(len(words), 0)

    def test_nested_tags(self):
        html = "<div><span><strong>Deep</strong> text</span></div>"
        _, text, _, _ = parse_html(html, "https://example.com")
        self.assertIn("Deep", text)
        self.assertIn("text", text)


class TestParseHtmlLinkExtraction(unittest.TestCase):
    """Tests for <a href> link extraction."""

    def test_absolute_link(self):
        html = '<a href="https://other.com/page">Link</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertIn("https://other.com/page", links)

    def test_relative_link(self):
        html = '<a href="/about">About</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertIn("https://example.com/about", links)

    def test_ignores_javascript_links(self):
        html = '<a href="javascript:void(0)">Click</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(links, [])

    def test_ignores_mailto_links(self):
        html = '<a href="mailto:test@example.com">Email</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(links, [])

    def test_ignores_fragment_only(self):
        html = '<a href="#section">Jump</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(links, [])

    def test_strips_fragment_from_url(self):
        html = '<a href="https://example.com/page#top">Link</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertIn("https://example.com/page", links)

    def test_deduplicates_links(self):
        html = '<a href="/page">A</a><a href="/page">B</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(len(links), 1)

    def test_multiple_distinct_links(self):
        html = '<a href="/one">A</a><a href="/two">B</a><a href="/three">C</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(len(links), 3)

    def test_ignores_tel_links(self):
        html = '<a href="tel:+1234567890">Call</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        self.assertEqual(links, [])


class TestParseHtmlWordCounting(unittest.TestCase):
    """Tests for word frequency counting."""

    def test_word_frequencies(self):
        html = "<p>hello hello world</p>"
        _, _, _, words = parse_html(html, "https://example.com")
        self.assertEqual(words["hello"], 2)
        self.assertEqual(words["world"], 1)

    def test_case_insensitive(self):
        html = "<p>Hello HELLO hello</p>"
        _, _, _, words = parse_html(html, "https://example.com")
        self.assertEqual(words["hello"], 3)

    def test_ignores_single_char_words(self):
        html = "<p>I a am good</p>"
        _, _, _, words = parse_html(html, "https://example.com")
        self.assertNotIn("i", words)
        self.assertNotIn("a", words)
        self.assertIn("am", words)
        self.assertIn("good", words)

    def test_ignores_numbers(self):
        html = "<p>year 2024 is great</p>"
        _, _, _, words = parse_html(html, "https://example.com")
        self.assertNotIn("2024", words)
        self.assertIn("year", words)
        self.assertIn("great", words)

    def test_empty_page_no_words(self):
        html = "<html><body></body></html>"
        _, _, _, words = parse_html(html, "https://example.com")
        self.assertEqual(len(words), 0)


class TestParseHtmlEdgeCases(unittest.TestCase):
    """Tests for malformed HTML and edge cases."""

    def test_malformed_html(self):
        html = "<p>Unclosed paragraph<div>Mixed</p></div>"
        title, text, links, words = parse_html(html, "https://example.com")
        # Should not crash — best-effort parsing
        self.assertIn("Unclosed", text)

    def test_no_body_tag(self):
        html = "Just plain text without any HTML tags"
        _, text, _, words = parse_html(html, "https://example.com")
        self.assertIn("plain", text)

    def test_empty_href(self):
        html = '<a href="">Empty</a>'
        _, _, links, _ = parse_html(html, "https://example.com")
        # Empty href resolves to base URL
        self.assertTrue(len(links) <= 1)

    def test_whitespace_only_text(self):
        html = "<p>   \n\t  </p>"
        _, text, _, words = parse_html(html, "https://example.com")
        self.assertEqual(len(words), 0)

    def test_special_characters_in_text(self):
        html = "<p>Hello &amp; welcome to the &quot;site&quot;</p>"
        _, text, _, words = parse_html(html, "https://example.com")
        self.assertIn("Hello", text)
        self.assertIn("welcome", text)


if __name__ == "__main__":
    unittest.main()
