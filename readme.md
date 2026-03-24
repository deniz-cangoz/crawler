# Web Crawler

This project is a localhost web crawler and search app built with Python, Flask, and SQLite.

## Features

- Crawl from any URL to a chosen depth.
- Control load with queue limits, request rate limits, and a max URL cap.
- Search indexed pages with relevance scoring.
- Keep search available while crawling is still running.
- Pause, resume, or stop crawl jobs from the UI.
- Export raw word data to `data/storage/p.data` for assignment checks.

## Quick Start

```bash
git clone https://github.com/deniz-cangoz/crawler.git
cd crawler
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://localhost:3600` in your browser.

## Using the App

### Start a crawl

- Open the home page at `/`.
- Enter an origin URL.
- Set depth, hit rate, max URLs, and queue capacity.
- Click `Start Crawl`.

### Check progress

- Open `/status/<crawl_id>`.
- Review pages crawled, queue size, and logs.
- Pause, resume, or stop the job if needed.

### Search indexed pages

- Open `/search`.
- Enter a query, or use `I'm Feeling Lucky`.
- Review the URL, origin URL, depth, and relevance score in the results.

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

# Pause, resume, or stop a crawl
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/pause
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/resume
curl -X POST http://localhost:3600/api/crawl/<crawl_id>/stop

# Search
curl "http://localhost:3600/search?query=python&sortBy=relevance"
curl "http://localhost:3600/api/search?query=python+web&limit=10&sort=relevance"

# Random word
curl http://localhost:3600/api/search/random

# System stats
curl http://localhost:3600/api/stats

# Clear all data
curl -X POST http://localhost:3600/api/clear
```

## Project Structure

```text
app.py
services/
  crawler_service.py
  search_service.py
utils/
  crawler_job.py
  html_parser.py
  database.py
templates/
static/
tests/
```

## Design Notes

- SQLite runs in WAL mode, so search can read while the crawler writes.
- Crawling uses the Python standard library, including `urllib`, `html.parser`, `threading`, and `queue`.
- Each crawl runs in its own daemon thread.
- Back pressure comes from queue limits, rate limits, and a max URL cap.
- Raw index data is also written to `data/storage/p.data`.

## API Reference

- `GET /search?query=...&sortBy=relevance` shows the assignment-friendly search route.
- `POST /api/crawl` starts a crawl with `origin`, `max_depth`, `hit_rate`, `max_urls`, and `max_queue`.
- `GET /api/crawl` lists crawl jobs.
- `GET /api/crawl/<id>` returns crawl status and logs.
- `POST /api/crawl/<id>/stop` stops a crawl.
- `POST /api/crawl/<id>/pause` pauses a crawl.
- `POST /api/crawl/<id>/resume` resumes a crawl.
- `GET /api/search?query=...` searches indexed pages.
- `GET /api/search/random` returns a random indexed word.
- `GET /api/stats` returns system statistics.
- `POST /api/clear` clears stored crawl data.

## Testing

```bash
python -m unittest discover tests/ -v
```

There are 55 unit tests. They cover:

- HTML parsing, text extraction, link extraction, and word counting
- Search behavior, sorting, pagination, and relevance scoring
- Crawl job lifecycle, controls, back pressure, and rate limiting

## Troubleshooting

- If port 3600 is busy, set `PORT=3601` before running, or change the port in `app.py`.
- If you hit SSL errors during a crawl, the crawler can fall back to unverified SSL for problematic sites.
- If search returns no results, check that at least one crawl has finished and written indexed data.
- If a crawl looks stuck, open the status page and review queue size and logs. Lowering `hit_rate` can help.

## Tech Stack

- Python 3
- Flask
- SQLite
- Vanilla HTML, CSS, and JavaScript
