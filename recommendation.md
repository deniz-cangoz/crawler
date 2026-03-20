# Recommendations for Production Deployment

## Storage

The current system uses SQLite, which works well for single-machine localhost deployment. For production, the storage layer should be split into purpose-built databases:

- **Crawl metadata and job state** should move to a key-value store like Redis or DynamoDB. These are write-heavy during crawling and benefit from in-memory speed. Job queues could leverage Redis Streams or a dedicated message broker (RabbitMQ, SQS) for distributed coordination.
- **The inverted word index** should be migrated to a dedicated search engine such as Elasticsearch or Meilisearch. These systems provide proper TF-IDF scoring, fuzzy matching, stemming, and sub-millisecond query latency at scale. The current alphabetical prefix matching is a reasonable starting point but lacks the sophistication needed for production-quality search results.
- **Visited URL tracking** should use a probabilistic data structure like a Bloom filter for fast membership checks during crawling, backed by a persistent store (PostgreSQL or BigQuery) for analytics and historical tracking.

## Scaling and Architecture

The crawler and search components should be deployed and scaled independently. The crawler is CPU and network-bound, while search is memory and I/O-bound — they have different scaling profiles.

For the crawler, the single-threaded-per-job model should evolve into a distributed worker architecture. A central scheduler distributes URL batches to worker nodes, which can be scaled horizontally across regions. Each worker should implement proper connection pooling, DNS caching, and respect `robots.txt` and `Crawl-Delay` directives. Back pressure should be extended to include memory/CPU-based throttling and per-domain rate limiting (not just global rate limiting) to be polite to target servers. For search, the inverted index should be sharded by word prefix or hash, with read replicas for availability. A caching layer (Redis/Memcached) for frequent queries would reduce latency significantly.

Additional production concerns include: monitoring and observability (Prometheus metrics for crawl throughput, queue depth, error rates; Grafana dashboards for operational visibility), compliance with robots.txt and legal requirements around web scraping, graceful degradation and circuit breakers for unreachable domains, and proper authentication/authorization for the management API.
