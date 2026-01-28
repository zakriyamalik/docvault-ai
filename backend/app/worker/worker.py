# backend/app/worker/worker.py
import os
import time
import logging

import redis
from rq import Worker, Queue
from rq.job import Job

# IMPORTANT: ensures RQ can resolve "tasks.ingest_document"
import app.tasks  # noqa: F401

# Structured logger
from app.logging import get_logger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# plain-text logger for bootstrap messages
logger = logging.getLogger("worker")
# structured logger for events
log = get_logger("worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")  # keep consistent with enqueue script
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


def job_failure_handler(job: Job, exc_type, exc_value, tb):
    # structured log for job failures or final failure after retries
    try:
        # job.meta may contain useful info; job.id is the RQ job id
        log.error(
            event="job_failure_handler",
            job_id=job.id,
            error=str(exc_value),
            job_meta=job.meta if hasattr(job, "meta") else None,
        )
    except Exception:
        logger.exception("Failed to log job failure handler")


def main():
    logger.info("Starting RQ worker")
    redis_conn = wait_for_redis(REDIS_URL)

    # Create Queue using the redis connection, and pass the connection
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    # Register our failure handler on the worker instance (after it's created)
    worker.push_exc_handler(job_failure_handler)

    # Start working (this will block)
    worker.work()


if __name__ == "__main__":
    main()
