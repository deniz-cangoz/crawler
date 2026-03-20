"""
HTML parser using Python's built-in html.parser module.
Extracts text content and links from HTML pages.

No external dependencies — uses only stdlib, as required by the assignment.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re
from collections import Counter


# Tags whose content we want to skip entirely
SKIP_TAGS = {"script", "style", "noscript", "svg"}


class _PageParser(HTMLParser):
    """
    Walks the HTML tree, collecting:
      - text  : visible text content (skipping script/style)
      - links : absolute URLs found in <a href="...">
      - title : content of <title> tag
    """

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.text_parts = []
        self.links = []
        self.title = ""
        self._skip_depth = 0       # > 0 means we're inside a SKIP_TAG
        self._in_title = False

    # ---- callbacks ----

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True

        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    abs_url = self._resolve(value)
                    if abs_url:
                        self.links.append(abs_url)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text)
            if self._in_title:
                self.title = text

    # ---- helpers ----

    def _resolve(self, href):
        """Resolve relative URL to absolute; drop fragments and non-http."""
        href = href.strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return None
        abs_url = urljoin(self.base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            return None
        # Strip fragment
        return parsed._replace(fragment="").geturl()


def parse_html(html_content, base_url):
    """
    Parse an HTML string and return (title, text, links, word_counts).

    Args:
        html_content: raw HTML string
        base_url: the URL of this page (for resolving relative links)

    Returns:
        title       : str — page title (or "")
        full_text   : str — visible text joined by spaces
        links       : list[str] — unique absolute URLs found on the page
        word_counts : Counter — {word: frequency} for words ≥ 2 chars
    """
    parser = _PageParser(base_url)
    try:
        parser.feed(html_content)
    except Exception:
        pass  # best-effort; malformed HTML is common

    full_text = " ".join(parser.text_parts)

    # Extract words (letters only, ≥ 2 chars), lowercase
    words = re.findall(r"\b[a-zA-Z]{2,}\b", full_text.lower())
    word_counts = Counter(words)

    # Deduplicate links while preserving order
    seen = set()
    unique_links = []
    for link in parser.links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return parser.title, full_text, unique_links, word_counts
