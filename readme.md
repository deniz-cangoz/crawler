# Web Crawler

A web crawler and search engine that runs on localhost. Built with Python, Flask, and SQLite.

## Features

- **Index**: BFS web crawl from any URL to configurable depth, with back pressure (bounded queue, rate limiting, URL cap)
- **Search**: Query indexed pages with relevance scoring, returns `(relevant_url, origin_url, depth)` triples
- **Live UI**: Start crawls, monitor progress with live logs, search indexed content
- **Resumable**: Crawls can be paused, stopped, and resumed without losing progress
- **Concurrent**: Search works while indexing is active (SQLite WAL mode)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/deniz-cangoz/crawler.git
cd crawler
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

Open http://localhost:3600 in your browser.

## Usage

### 1. Start a Crawl
- Go to the home page (`/`)
- Enter a URL (e.g., `https://en.wikipedia.org/wiki/Web_crawler`)
- Set depth, hit rate, max URLs, and queue capacity
- Click "Start Crawl"

### 2. Monitor Progress
- You'll be redirected to the status page (`/status/<crawl_id>`)
- See live stats: pages crawled, queue size, status
- View real-time logs
- Pause, resume, or stop the crawl

### 3. Search
- Go to the search page (`/search`)
- Enter keywords (or click "I'm Feeling Lucky" for a random word)
- Results show: URL, origin URL, depth, relevance score

## API Examples

```bash
# Start a crawl
curl -X POST http://localhost:3600/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"origin": "https://example.com", "max_depth": 2, "hit_rate": 10, "max_urls": 500}'

# Check crawl status
curl http://localhost:3600/api/crawl/<crawl_id>

# List all crawls
curl http://localhost:3600/api/crawl

# Pause / Resume / Stop a crawl
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/pause
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/resume
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/stop

# Search
curl "http://localhost:3600/search?query=python&sortBy=relevance"
curl "http://localhost:3600/api/search?query=python+web&limit=10&sort=relevance"

# Random word (I'm Feeling Lucky)
curl http://localhost:3600/api/search/random

# System stats
curl http://localhost:3600/api/stats

# Clear all data
curl -X POST http://localhost:3600/api/clear
```

## Architecture

```
app.py                  # Flask routes (API + pages)
services/
  crawler_service.py    # Crawler lifecycle management
  search_service.py     # Search query processing
utils/
  crawler_job.py        # Threaded BFS crawler engine
  html_parser.py        # stdlib HTML parser (no BeautifulSoup)
  database.py           # SQLite with WAL mode
templates/              # Jinja2 HTML templates
static/                 # CSS and JavaScript
tests/                  # Unit tests
```

### Key Design Decisions

- **SQLite with WAL mode**: Allows search to read while crawler writes — no blocking
- **stdlib only for crawling**: Uses `urllib`, `html.parser`, `threading`, `queue` — no external crawling libraries
- **Thread-per-crawl**: Each crawl runs as a daemon thread; simple and predictable
- **Bounded queue + rate limiting**: Back pressure prevents uncontrolled resource usage
- **Inverted index in SQL**: B-tree indexed word lookups with prefix matching support
- **Assignment raw storage export**: indexed data is also written to `data/storage/p.data`

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/crawl` | Start crawl `{origin, max_depth, hit_rate, max_urls, max_queue}` |
| GET | `/api/crawl` | List all crawls |
| GET | `/api/crawl/<id>` | Crawl status + logs |
| POST | `/api/crawl/<id>/stop` | Stop crawl |
| POST | `/api/crawl/<id>/pause` | Pause crawl |
| POST | `/api/crawl/<id>/resume` | Resume crawl |
| GET | `/api/search?query=...` | Search indexed pages |
| GET | `/api/search/random` | Random word (I'm Feeling Lucky) |
| GET | `/api/stats` | System statistics |
| POST | `/api/clear` | Clear all data |

## Testing

```bash
# Run all tests
python -m unittest discover tests/ -v
```

54 unit tests covering:
- HTML parser (text extraction, link extraction, word counting, edge cases)
- Search service (exact match, prefix match, multi-word, pagination, sorting)
- Crawler job (initialization, controls, back pressure, rate limiting)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 5000 in use | Change port in `app.py`: `app.run(port=5001)` |
| SSL errors during crawl | The crawler has a fallback to unverified SSL for problematic sites |
| No search results | Make sure a crawl has completed first — search queries the indexed data |
| Crawl seems stuck | Check the status page for queue size and logs. Try reducing `hit_rate` |

## Tech Stack

- Python 3
- Flask (web framework)
- SQLite (database)
- Vanilla HTML/CSS/JS (frontend)
