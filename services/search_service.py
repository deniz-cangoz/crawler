"""
Search service — queries the word_index to find relevant URLs.

Assignment-compatible relevancy model:
  - Exact match score = (frequency * 10) + 1000 - (depth * 5)
  - Prefix matches are only used when no exact match exists for that query word
  - Results are grouped by URL to avoid duplicates
  - The API returns both `relevance_score` and legacy `score`

Returns triples: (relevant_url, origin_url, depth) as required.
"""

from utils.database import get_connection
import re
import random


def _ensure_result(url_scores, row):
    """Create the grouped result object for a URL if needed."""
    key = row["url"]
    if key not in url_scores:
        url_scores[key] = {
            "url": row["url"],
            "origin_url": row["origin_url"],
            "depth": row["depth"],
            "relevance_score": 0,
            "total_frequency": 0,
            "matched_words": set(),
            "match_types": set(),
        }
    return url_scores[key]


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
        # Group scores by URL while keeping the current origin/depth metadata.
        url_scores = {}  # url -> aggregated metadata

        for word in words:
            exact_rows = conn.execute(
                """SELECT url, origin_url, depth, frequency
                   FROM word_index WHERE word = ?""",
                (word,),
            ).fetchall()

            if exact_rows:
                for row in exact_rows:
                    result = _ensure_result(url_scores, row)
                    result["relevance_score"] += (
                        row["frequency"] * 10 + 1000 - row["depth"] * 5
                    )
                    result["total_frequency"] += row["frequency"]
                    result["matched_words"].add(word)
                    result["match_types"].add("exact")
                continue

            rows = conn.execute(
                """SELECT url, origin_url, depth, frequency
                   FROM word_index WHERE word LIKE ? AND word != ?""",
                (word + "%", word),
            ).fetchall()

            for row in rows:
                result = _ensure_result(url_scores, row)
                result["relevance_score"] += row["frequency"] * 10 - row["depth"] * 5
                result["total_frequency"] += row["frequency"]
                result["matched_words"].add(word)
                result["match_types"].add("prefix")

        # Convert to list and sort
        results = list(url_scores.values())

        for r in results:
            r["matched_words"] = sorted(r["matched_words"])
            r["match_types"] = sorted(r["match_types"])

        # Sort
        if sort_by == "depth":
            results.sort(key=lambda r: (r["depth"], -r["relevance_score"], r["url"]))
        elif sort_by == "frequency":
            results.sort(
                key=lambda r: (r["total_frequency"], r["relevance_score"], -r["depth"], r["url"]),
                reverse=True,
            )
        else:  # relevance (default)
            results.sort(
                key=lambda r: (r["relevance_score"], r["total_frequency"], -r["depth"], r["url"]),
                reverse=True,
            )

        total = len(results)

        # Paginate
        results = results[page_offset: page_offset + page_limit]

        # Format output as triples + extra info
        formatted = [
            {
                "relevant_url": r["url"],
                "url": r["url"],
                "origin_url": r["origin_url"],
                "depth": r["depth"],
                "relevance_score": r["relevance_score"],
                "score": r["relevance_score"],
                "total_frequency": r["total_frequency"],
                "matched_words": r["matched_words"],
                "match_types": r["match_types"],
            }
            for r in results
        ]

        return {
            "results": formatted,
            "total_results": total,
            "query_words": words,
            "sort_by": sort_by,
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
