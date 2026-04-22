import os
import uuid

import redis
from fastapi import FastAPI, HTTPException

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

app = FastAPI(title="Job API")

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


@app.get("/health")
def health():
    try:
        r.ping()
    except redis.exceptions.RedisError:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"status": "ok"}


@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    r.hset(f"job:{job_id}", "status", "queued")
    r.lpush("job", job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        raise HTTPException(status_code=404, detail="not found")
    return {"job_id": job_id, "status": status}
