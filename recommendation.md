# Recommendations for Production Deployment

For production, I would split crawling and search into separate services. SQLite works well for localhost, but production needs storage built for each job. Crawl state and frontier data can move to a durable queue or key-value store such as Redis or SQS. The search index can move to a dedicated engine such as Elasticsearch, OpenSearch, or Meilisearch. This keeps the current structure, while making search faster and crawl coordination more reliable.

I would also add stronger operational controls. The next steps are per-domain rate limits, `robots.txt` support, retry policies, and clear metrics for crawl throughput, queue depth, indexing lag, and query latency. After that, the single-machine worker model can move to a distributed worker pool without changing the public API or search flow.
