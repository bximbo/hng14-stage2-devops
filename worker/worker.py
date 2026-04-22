import os
import signal
import sys
import time

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

running = True


def handle_shutdown(signum, frame):
    global running
    print(f"Received signal {signum}, shutting down gracefully...")
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


def process_job(job_id):
    print(f"Processing job {job_id}")
    r.hset(f"job:{job_id}", "status", "processing")
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}")


backoff = 1
max_backoff = 32

while running:
    try:
        job = r.brpop("job", timeout=5)
        if job:
            _, job_id = job
            backoff = 1
            process_job(job_id)
    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection error: {e}, retrying in {backoff}s...")
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        time.sleep(1)

print("Worker shutdown complete")
