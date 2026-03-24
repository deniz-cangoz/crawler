# Product Requirements Document: Web Crawler

## Overview

This project has two main capabilities: index and search. The index side crawls pages from a given URL up to a chosen depth. The search side returns relevant URLs for a text query. The system also includes a small web UI for starting crawls, checking progress, and searching indexed content.

## Core Requirements

### 1. Index

Route:
- `POST /api/crawl`

Inputs:
- `origin` for the starting URL
- `max_depth` for the hop limit
- `hit_rate`, `max_queue`, and `max_urls` for load control

Behavior:
- Uses breadth-first traversal from the origin URL up to depth `k`
- Avoids revisiting the same URL
- Runs each crawl in its own daemon thread

Load control:
- A bounded queue stops new items when the queue is full
- Rate limiting controls requests per second
- A max URL cap stops very large crawls

Storage:
- Uses SQLite with WAL mode for concurrent reads and writes
- Writes raw storage lines to `data/storage/p.data` for assignment checks

### 2. Search

Routes:
- `GET /api/search`
- `GET /search?query=...&sortBy=relevance`

Input:
- Query string
- Pagination values
- Sort option

Output:
- A list of `(relevant_url, origin_url, depth)` results
- A `relevance_score` field for ranking

Ranking:
- Exact matches use `(frequency * 10) + 1000 - (depth * 5)`
- Prefix fallback is used only if there is no exact match for that query word
- Results are grouped by URL and sorted by `relevance_score`

Runtime behavior:
- Search stays available while indexing is active because SQLite WAL mode allows concurrent reads

### 3. UI

Flask serves three pages:

- `/` starts new crawls and shows summary stats
- `/status/<id>` shows live crawl status, logs, and controls
- `/search` searches indexed pages with sorting and pagination

### 4. System State Visibility

- Total jobs, indexed pages, unique words, and active crawlers are visible on the dashboard
- Each crawl has live logs that update during execution
- Queue depth is visible on the status page
- Back pressure state is shown on the status page through queue usage

### 5. Resumability

- Queue state is persisted to the database when a crawl stops
- The resume endpoint re-creates the thread with the saved queue
- Visited URLs are loaded from the `pages` table on resume

## Architecture

```text
app.py
  Flask routes and HTML pages
services/
  crawler_service.py
  search_service.py
utils/
  crawler_job.py
  html_parser.py
  database.py
static/
templates/
```

## Technology Choices

- Python 3 and Flask keep the project small and easy to run on localhost
- SQLite gives simple local storage with WAL mode for concurrent access
- Crawling uses the Python standard library, not external crawler frameworks
- The frontend uses plain HTML, CSS, and JavaScript

## API Reference

- `POST /api/crawl` starts a new crawl
- `GET /api/crawl` lists crawl jobs
- `GET /api/crawl/<id>` returns crawl status and logs
- `POST /api/crawl/<id>/stop` stops a crawl
- `POST /api/crawl/<id>/pause` pauses a crawl
- `POST /api/crawl/<id>/resume` resumes a crawl
- `GET /search?query=...&sortBy=relevance` supports the assignment search flow
- `GET /api/search?query=...` searches indexed pages
- `GET /api/stats` returns system statistics
- `POST /api/clear` clears stored data

## Design Decisions

1. SQLite was chosen over flat files because search needs to keep working while indexing is active.
2. Each crawl runs in its own thread. This keeps the job model simple.
3. The inverted index lives in the `word_index` table, which keeps lookups fast and supports simple prefix fallback.
4. Crawling uses only Python standard library modules such as `urllib.request`, `html.parser.HTMLParser`, `threading`, and `queue`.
