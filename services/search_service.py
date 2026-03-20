"""
Search service — queries the word_index to find relevant URLs.

Relevancy model (simple but effective):
  - Each query word is searched in the word_index table
  - Scoring = sum of word frequencies across matching pages
  - Exact word match scores higher than prefix match
  - Results are grouped by URL to avoid duplicates

Returns triples: (relevant_url, origin_url, depth) as required.
"""

from utils.database import get_connection
import re
import random


def search(query, page_limit=20, page_offset=0, sort_by="relevance"):
    """
    Search indexed pages for the given query.

    Args:
        query: search string (split into words)
        page_limit: pagination size
        page_offset: pagination offset
        sort_by: "relevance" (default), "frequency", or "depth"

    Returns:
        dict with results list, total count, and metadata
    """
    # Normalize query into words
    words = re.findall(r"\b[a-zA-Z]{2,}\b", query.lower())
    if not words:
        return {"results": [], "total_results": 0, "query_words": []}

    conn = get_connection()
    try:
        # Build a query that scores each URL by total frequency of matching words.
        # We use LIKE for prefix matching: 'prog' matches 'programming'.
        # Exact matches get a 10x bonus.

        # For each word, find matching entries
        url_scores = {}  # url → {score, origin_url, depth, matched_words}

        for word in words:
            # Exact match
            rows = conn.execute(
                """SELECT url, origin_url, depth, frequency
                   FROM word_index WHERE word = ?""",
                (word,),
            ).fetchall()

            for row in rows:
                key = row["url"]
                if key not in url_scores:
                    url_scores[key] = {
                        "url": row["url"],
                        "origin_url": row["origin_url"],
                        "depth": row["depth"],
                        "score": 0,
                        "matched_words": set(),
                    }
                url_scores[key]["score"] += row["frequency"] * 10  # exact bonus
                url_scores[key]["matched_words"].add(word)

            # Prefix match (words starting with query word, but not exact)
            rows = conn.execute(
                """SELECT url, origin_url, depth, frequency
                   FROM word_index WHERE word LIKE ? AND word != ?""",
                (word + "%", word),
            ).fetchall()

            for row in rows:
                key = row["url"]
                if key not in url_scores:
                    url_scores[key] = {
                        "url": row["url"],
                        "origin_url": row["origin_url"],
                        "depth": row["depth"],
                        "score": 0,
                        "matched_words": set(),
                    }
                url_scores[key]["score"] += row["frequency"]
                url_scores[key]["matched_words"].add(word)

        # Convert to list and sort
        results = list(url_scores.values())

        # Bonus for matching more query words
        for r in results:
            r["score"] += len(r["matched_words"]) * 100
            r["matched_words"] = list(r["matched_words"])  # set → list for JSON

        # Sort
        if sort_by == "depth":
            results.sort(key=lambda r: r["depth"])
        elif sort_by == "frequency":
            results.sort(key=lambda r: r["score"], reverse=True)
        else:  # relevance (default) — score with depth penalty
            results.sort(key=lambda r: r["score"] - r["depth"] * 5, reverse=True)

        total = len(results)

        # Paginate
        results = results[page_offset: page_offset + page_limit]

        # Format output as triples + extra info
        formatted = [
            {
                "relevant_url": r["url"],
                "origin_url": r["origin_url"],
                "depth": r["depth"],
                "score": r["score"],
                "matched_words": r["matched_words"],
            }
            for r in results
        ]

        return {
            "results": formatted,
            "total_results": total,
            "query_words": words,
        }

    finally:
        conn.close()


def get_random_word():
    """
    Pick a random indexed word for "I'm Feeling Lucky" feature.
    Returns the word so the frontend can auto-search it.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT DISTINCT word FROM word_index ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        if not row:
            return {"error": "No indexed words yet"}
        return {"word": row["word"]}
    finally:
        conn.close()
