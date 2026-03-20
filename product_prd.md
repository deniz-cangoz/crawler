# Product Requirements Document — Web Crawler

## Overview
A web crawler system that exposes two core capabilities: **index** (crawl web pages from a given URL to a specified depth) and **search** (find relevant URLs based on a text query). The system includes a web-based UI for initiating crawls, monitoring progress, and searching indexed content.

## Core Requirements

### 1. Index (`POST /api/crawl`)
- **Parameters**: `origin` (URL), `max_depth` (k hops), `hit_rate`, `max_queue`, `max_urls`
- **BFS traversal**: Breadth-first search from origin URL up to depth k
- **Deduplication**: Never crawl the same URL twice (tracked via visited set + DB)
- **Back pressure mechanisms**:
  - Bounded queue (`queue.Queue(maxsize)`) — stops enqueueing when full
  - Rate limiting — configurable requests per second with sleep-based throttle
  - Max URL cap — hard stop after N pages crawled
- **Concurrency**: Each crawl runs as a daemon thread; multiple crawls can run simultaneously
- **Storage**: SQLite with WAL mode for concurrent read/write access

### 2. Search (`GET /api/search`)
- **Input**: Query string, pagination params, sort option
- **Output**: List of triples `(relevant_url, origin_url, depth)` with relevance score
- **Relevancy model**:
  - Word frequency scoring (exact match 10x bonus)
  - Prefix matching for partial word matches
  - Multi-word query bonus (matching more words = higher score)
  - Depth penalty (shallower pages ranked higher)
- **Real-time**: Search works while indexing is active (SQLite WAL mode enables concurrent reads)

### 3. UI (Web Interface)
Three pages served by Flask:

| Page | Purpose |
|------|---------|
| `/` (Crawler) | Start new crawls, view stats, see recent jobs |
| `/status/<id>` | Live crawl status with logs, pause/resume/stop controls |
| `/search` | Search indexed pages with pagination and sorting |

### 4. System State Visibility
- **Stats dashboard**: Total jobs, pages indexed, unique words, active crawlers
- **Live logs**: Real-time log entries for each crawl (polled every 2 seconds)
- **Queue depth**: Visible on status page
- **Back pressure status**: Logged when queue is full

### 5. Resumability
- Queue state is persisted to DB when a crawl stops
- Resume endpoint re-creates the thread with saved queue
- Visited URLs are loaded from the pages table on resume

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Flask App (app.py)                             │
│  REST API + serves HTML templates               │
├─────────────────────────────────────────────────┤
│  Services Layer                                 │
│  ├── crawler_service.py  (job lifecycle)        │
│  └── search_service.py   (query processing)     │
├─────────────────────────────────────────────────┤
│  Utils Layer                                    │
│  ├── crawler_job.py      (threaded BFS engine)  │
│  ├── html_parser.py      (stdlib HTML parsing)  │
│  └── database.py         (SQLite + WAL)         │
├─────────────────────────────────────────────────┤
│  Frontend (vanilla HTML/CSS/JS)                 │
│  ├── templates/  (Jinja2 templates)             │
│  └── static/     (CSS + JS)                     │
└─────────────────────────────────────────────────┘
```

## Technology Choices
- **Python 3 + Flask**: Minimal framework, easy to run on localhost
- **SQLite**: Zero-config database, WAL mode for concurrent access
- **stdlib only for crawling**: `urllib`, `html.parser`, `threading`, `queue` — no BeautifulSoup, no requests, no Scrapy
- **Vanilla HTML/CSS/JS**: No React/Vue/build step needed

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/crawl` | Start a new crawl |
| GET | `/api/crawl` | List all crawl jobs |
| GET | `/api/crawl/<id>` | Get crawl status + logs |
| POST | `/api/crawl/<id>/stop` | Stop a crawl |
| POST | `/api/crawl/<id>/pause` | Pause a crawl |
| POST | `/api/crawl/<id>/resume` | Resume a crawl |
| GET | `/api/search?query=...` | Search indexed pages |
| GET | `/api/stats` | System statistics |
| POST | `/api/clear` | Clear all data |

## Design Decisions

1. **SQLite over flat files**: The assignment requires search to work while indexing is active. SQLite WAL mode handles this naturally. Flat files would require file locking and re-sorting.

2. **Thread-per-crawl (not thread pool within a crawl)**: Keeps the implementation simple and predictable. Multiple concurrent crawls are supported by starting multiple threads.

3. **Inverted index in SQL**: Word → URL mapping stored in `word_index` table with B-tree indexes. Enables prefix matching via `LIKE 'word%'` which SQLite optimizes with the index.

4. **No external crawling libraries**: As required, uses only Python stdlib (`urllib.request`, `html.parser.HTMLParser`, `threading`, `queue`).
