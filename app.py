"""
Flask application — REST API + serves the frontend.

Endpoints:
  POST /api/crawl          → start a new crawl
  GET  /api/crawl          → list all crawl jobs
  GET  /api/crawl/<id>     → get crawl status + logs
  POST /api/crawl/<id>/stop   → stop a crawl
  POST /api/crawl/<id>/pause  → pause a crawl
  POST /api/crawl/<id>/resume → resume a crawl
  GET  /api/search         → search indexed pages
  GET  /api/stats          → system statistics
  POST /api/clear          → clear all data

Pages:
  /           → crawler page (start new crawls)
  /status     → crawler status page
  /search     → search page
"""

from flask import Flask, request, jsonify, render_template
from urllib.parse import urlparse
from services import crawler_service, search_service

app = Flask(__name__)


# ---- CORS ----
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


# ---- Helper ----
def is_valid_url(url):
    try:
        r = urlparse(url)
        return all([r.scheme in ("http", "https"), r.netloc])
    except Exception:
        return False


# ============================================================
#  API ENDPOINTS
# ============================================================

@app.route("/api/crawl", methods=["POST"])
def create_crawl():
    """Start a new crawl job."""
    data = request.get_json(silent=True) or {}

    origin = (data.get("origin") or "").strip()
    if not origin or not is_valid_url(origin):
        return jsonify({"error": "Valid URL required (including http/https)"}), 400

    max_depth = data.get("max_depth", 2)
    if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 100:
        return jsonify({"error": "max_depth must be 1-100"}), 400

    hit_rate = data.get("hit_rate", 10.0)
    max_queue = data.get("max_queue", 10000)
    max_urls = data.get("max_urls", 500)

    result = crawler_service.create_crawler(
        origin=origin,
        max_depth=max_depth,
        hit_rate=hit_rate,
        max_queue=max_queue,
        max_urls=max_urls,
    )
    return jsonify(result), 201


@app.route("/api/crawl", methods=["GET"])
def list_crawls():
    """List all crawl jobs."""
    return jsonify(crawler_service.list_crawlers())


@app.route("/api/crawl/<crawl_id>", methods=["GET"])
def crawl_status(crawl_id):
    """Get status + logs for a specific crawl."""
    status = crawler_service.get_crawler_status(crawl_id)
    if "error" in status:
        return jsonify(status), 404
    logs = crawler_service.get_crawler_logs(crawl_id, limit=50)
    status["logs"] = logs
    return jsonify(status)


@app.route("/api/crawl/<crawl_id>/stop", methods=["POST"])
def stop_crawl(crawl_id):
    result = crawler_service.stop_crawler(crawl_id)
    code = 200 if "error" not in result else 404
    return jsonify(result), code


@app.route("/api/crawl/<crawl_id>/pause", methods=["POST"])
def pause_crawl(crawl_id):
    result = crawler_service.pause_crawler(crawl_id)
    code = 200 if "error" not in result else 404
    return jsonify(result), code


@app.route("/api/crawl/<crawl_id>/resume", methods=["POST"])
def resume_crawl(crawl_id):
    result = crawler_service.resume_crawler(crawl_id)
    code = 200 if "error" not in result else 404
    return jsonify(result), code


@app.route("/api/search", methods=["GET"])
def search():
    """Search indexed pages."""
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "query parameter required"}), 400

    page_limit = request.args.get("limit", 20, type=int)
    page_offset = request.args.get("offset", 0, type=int)
    sort_by = request.args.get("sort", "relevance")

    result = search_service.search(query, page_limit, page_offset, sort_by)
    return jsonify(result)


@app.route("/api/stats", methods=["GET"])
def stats():
    """System statistics."""
    return jsonify(crawler_service.get_statistics())


@app.route("/api/clear", methods=["POST"])
def clear():
    """Clear all data."""
    return jsonify(crawler_service.clear_all_data())


# ============================================================
#  FRONTEND PAGES
# ============================================================

@app.route("/")
def index_page():
    return render_template("index.html")


@app.route("/status")
@app.route("/status/<crawl_id>")
def status_page(crawl_id=None):
    return render_template("status.html")


@app.route("/search")
def search_page():
    return render_template("search.html")


# ============================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
