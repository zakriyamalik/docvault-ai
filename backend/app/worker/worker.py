import os
import time
import logging

import redis
from rq import Worker, Queue  # do not import Connection to avoid ImportError

# IMPORTANT: ensures RQ can resolve "tasks.ingest_document"
import app.tasks  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
QUEUE_NAME = os.getenv("RQ_QUEUE", "ingest")


def wait_for_redis(url, retries=10, delay=3):
    for attempt in range(1, retries + 1):
        try:
            conn = redis.from_url(url)
            conn.ping()
            logger.info("Connected to Redis")
            return conn
        except Exception as e:
            logger.warning(
                "Redis not ready (attempt %d/%d): %s",
                attempt,
                retries,
                e,
            )
            time.sleep(delay)
    raise RuntimeError("Redis not available")


def main():
    logger.info("Starting RQ worker")
    redis_conn = wait_for_redis(REDIS_URL)

    # Create Queue using the redis connection, and pass the connection
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    # Start working (this will block)
    worker.work()


if __name__ == "__main__":
    main()
