"""
Helper for answering the assignment questions from local crawler data.

Usage:
    python tools/assignment_report.py
    python tools/assignment_report.py --word python
    python tools/assignment_report.py --word python --host http://127.0.0.1:3600
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STORAGE_PATH = os.path.join(PROJECT_ROOT, "data", "storage", "p.data")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate assignment-ready search evidence from p.data.")
    parser.add_argument("--word", help="Specific word to inspect. If omitted, a candidate is selected automatically.")
    parser.add_argument("--host", default="http://127.0.0.1:3600", help="Local server base URL.")
    return parser.parse_args()


def load_entries(path):
    entries = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"Raw storage file not found: {path}")

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            parts = raw.split()
            if len(parts) != 5:
                raise ValueError(f"Malformed line {line_number}: {raw}")
            word, url, origin_url, depth, frequency = parts
            entries.append(
                {
                    "word": word,
                    "url": url,
                    "origin_url": origin_url,
                    "depth": int(depth),
                    "frequency": int(frequency),
                    "raw": raw,
                }
            )
    return entries


def pick_candidate_word(entries):
    grouped = defaultdict(list)
    distinct_urls = defaultdict(set)
    total_frequency = defaultdict(int)

    for entry in entries:
        grouped[entry["word"]].append(entry)
        distinct_urls[entry["word"]].add(entry["url"])
        total_frequency[entry["word"]] += entry["frequency"]

    candidates = []
    for word, rows in grouped.items():
        url_count = len(distinct_urls[word])
        if url_count >= 3:
            candidates.append((url_count, total_frequency[word], word, rows))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return candidates[0][2]


def score_entry(entry):
    return (entry["frequency"] * 10) + 1000 - (entry["depth"] * 5)


def query_api(host, word):
    query = urllib.parse.urlencode(
        {
            "query": word,
            "sortBy": "relevance",
            "format": "json",
        }
    )
    url = f"{host}/search?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    args = parse_args()
    entries = load_entries(STORAGE_PATH)
    if not entries:
        print("No data found in data/storage/p.data. Run a crawl first.")
        return 1

    word = args.word or pick_candidate_word(entries)
    if not word:
        print("No word appears on at least 3 distinct URLs yet. Crawl more pages first.")
        return 1

    selected = [entry for entry in entries if entry["word"] == word]
    selected.sort(key=lambda item: (score_entry(item), item["frequency"], -item["depth"], item["url"]), reverse=True)
    top_three = selected[:3]

    print(f"Chosen word: {word}")
    print()
    for index, entry in enumerate(top_three, start=1):
        print(f"Entry {index}: {entry['raw']}")
    print()
    for index, entry in enumerate(top_three, start=1):
        score = score_entry(entry)
        print(
            f"Entry {index} score: ({entry['frequency']} x 10) + 1000 - "
            f"({entry['depth']} x 5) = {score}"
        )

    try:
        api_result = query_api(args.host, word)
    except Exception as exc:
        print()
        print(f"API query failed: {exc}")
        return 0

    print()
    if not api_result.get("results"):
        print("API returned no results for that word.")
        return 0

    top_result = api_result["results"][0]
    print(f"API #1 URL: {top_result['relevant_url']}")
    print(f"API #1 relevance_score: {top_result['relevance_score']}")
    print(f"Matches highest manual score: {'Yes' if score_entry(top_three[0]) == top_result['relevance_score'] and top_three[0]['url'] == top_result['relevant_url'] else 'No'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
