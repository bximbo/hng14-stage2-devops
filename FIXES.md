# Bug Fixes Documentation

This document lists every bug found in the starter code and how each was fixed.

## 1. API Redis Hardcoded Hostname (api/main.py:8)

**Problem:** Redis connection hardcoded to `localhost:6379`, which fails inside containers where services communicate via DNS names on the internal network.

**Before:**
```python
r = redis.Redis(host="localhost", port=6379)
```

**After:**
```python
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
```

**Rationale:** Environment-driven configuration allows the same image to work locally (localhost) and in containers (service name). `decode_responses=True` prevents bytes-decoding bugs downstream.

---

## 2. API Missing /health Endpoint

**Problem:** Docker compose and container health checks require an accessible HTTP health endpoint; without it, `depends_on: {condition: service_healthy}` cannot work.

**Before:** No endpoint.

**After:**
```python
@app.get("/health")
def health():
    try:
        r.ping()
    except redis.exceptions.RedisError:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"status": "ok"}
```

**Rationale:** Pinging Redis ensures the critical dependency is reachable before declaring the service healthy.

---

## 3. API Missing Job Returns HTTP 200 (api/main.py:20–22)

**Problem:** Requesting a non-existent job returns HTTP 200 with `{"error": "not found"}`, masking failures and breaking API contracts.

**Before:**
```python
@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        return {"error": "not found"}
    return {"job_id": job_id, "status": status.decode()}
```

**After:**
```python
@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        raise HTTPException(status_code=404, detail="not found")
    return {"job_id": job_id, "status": status}
```

**Rationale:** HTTP 404 correctly signals "not found" and lets clients handle missing jobs properly.

---

## 4. API Race Condition: LPUSH Before HSET (api/main.py:13–14)

**Problem:** The worker can pop a job from the queue and attempt to process it before the job's hash (status field) is written, causing a race condition where the worker reads a non-existent job.

**Before:**
```python
@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    r.lpush("job", job_id)  # Job in queue
    r.hset(f"job:{job_id}", "status", "queued")  # Status written after
    return {"job_id": job_id}
```

**After:**
```python
@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    r.hset(f"job:{job_id}", "status", "queued")  # Status written first
    r.lpush("job", job_id)  # Only then add to queue
    return {"job_id": job_id, "status": "queued"}
```

**Rationale:** Writing the job state before enqueuing it ensures the worker always finds a valid job record.

---

## 5. API Assumes Bytes Response (api/main.py:22)

**Problem:** Without `decode_responses=True`, `r.hget()` returns bytes, and `.decode()` is needed on every response; this is error-prone and redundant.

**Before:**
```python
return {"job_id": job_id, "status": status.decode()}
```

**After:**
```python
r = redis.Redis(..., decode_responses=True, ...)
return {"job_id": job_id, "status": status}  # Already a string
```

**Rationale:** Setting `decode_responses=True` on the Redis client ensures all responses are strings, simplifying code and reducing decoding bugs.

---

## 6. Worker Redis Hardcoded Hostname (worker/worker.py:6)

**Problem:** Same as bug #1 — hardcoded `localhost` breaks in containers.

**Before:**
```python
r = redis.Redis(host="localhost", port=6379)
```

**After:**
```python
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
```

**Rationale:** Same as bug #1.

---

## 7. Worker Missing SIGTERM Handler (worker/worker.py:4)

**Problem:** The worker imports `signal` but never installs a handler. When Docker sends SIGTERM during shutdown, the worker is forcefully killed (SIGKILL) instead of exiting gracefully.

**Before:**
```python
import signal
# ... rest of code, no signal handling
while True:
    job = r.brpop("job", timeout=5)
    # ...
```

**After:**
```python
import signal

running = True

def handle_shutdown(signum, frame):
    global running
    print(f"Received signal {signum}, shutting down gracefully...")
    running = False

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

while running:
    try:
        job = r.brpop("job", timeout=5)
        if job:
            _, job_id = job
            process_job(job_id)
    except Exception as e:
        # ...

print("Worker shutdown complete")
```

**Rationale:** Graceful shutdown allows the worker to finish processing a job and release resources cleanly, reducing data loss and improving reliability.

---

## 8. Worker No Reconnect on Connection Error (worker/worker.py:14–18)

**Problem:** A transient Redis connection failure (e.g., Redis restart) crashes the worker with no retry logic; the container must be restarted manually.

**Before:**
```python
while True:
    job = r.brpop("job", timeout=5)
    if job:
        _, job_id = job
        process_job(job_id.decode())
```

**After:**
```python
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
```

**Rationale:** Exponential backoff (capped at 32s) allows the worker to survive transient outages without overwhelming the system with rapid retries.

---

## 9. Worker Missing "processing" Status (worker/worker.py)

**Problem:** The job transitions directly from "queued" to "completed", with no intermediate "processing" state; the UI cannot show progress.

**Before:**
```python
def process_job(job_id):
    print(f"Processing job {job_id}")
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}")
```

**After:**
```python
def process_job(job_id):
    print(f"Processing job {job_id}")
    r.hset(f"job:{job_id}", "status", "processing")
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}")
```

**Rationale:** The intermediate "processing" state allows clients to see job progress and distinguish between "queued but not yet running" and "actively processing".

---

## 10. Frontend Hardcoded API URL (frontend/app.js:6)

**Problem:** API URL hardcoded to `http://localhost:8000`, which fails in containers where the API service is named `api` and accessible via `http://api:8000`.

**Before:**
```javascript
const API_URL = "http://localhost:8000";
```

**After:**
```javascript
const API_URL = process.env.API_URL || 'http://api:8000';
```

**Rationale:** Environment-driven configuration allows the same image to work locally and in containers.

---

## 11. Frontend Hardcoded Port (frontend/app.js:29)

**Problem:** Port 3000 hardcoded in the app.listen() call, preventing deployment on alternative ports.

**Before:**
```javascript
app.listen(3000, () => {
  console.log('Frontend running on port 3000');
});
```

**After:**
```javascript
const PORT = parseInt(process.env.PORT || '3000', 10);
app.listen(PORT, () => {
  console.log(`Frontend running on port ${PORT}`);
});
```

**Rationale:** Environment-driven port configuration enables flexible deployment.

---

## 12. Frontend Missing /health Endpoint

**Problem:** No health check endpoint prevents container health verification.

**Before:** No endpoint.

**After:**
```javascript
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});
```

**Rationale:** A simple health endpoint allows Docker and orchestration tools to verify the frontend is running.

---

## 13. API .env File Committed with Secret (api/.env)

**Problem:** The file `api/.env` was committed to git with a real password `REDIS_PASSWORD=supersecretpassword123`, exposing the secret in all clones and forks.

**Fix:** 
1. Deleted `api/.env` from the working directory.
2. Ran `git filter-repo --path api/.env --invert-paths --force` to purge the file from all commits in the feature branch.
3. Added `.env` to `.gitignore` so no `.env` files are accidentally committed.
4. Created `.env.example` with placeholders for users to copy and populate locally.

**Rationale:** Secrets must never be in version control. Even after deletion, they persist in git history unless explicitly purged.

---

## 14. API Requirements Unpinned (api/requirements.txt)

**Problem:** Dependencies listed without versions (e.g., `fastapi` instead of `fastapi==0.104.1`), causing unreproducible builds when versions are bumped.

**Before:**
```
fastapi
uvicorn
redis
```

**After:**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
redis==5.0.1
```

**Rationale:** Pinned versions ensure consistent builds and deployments across environments.

---

## 15. API Test Dependencies Missing (requirements-dev.txt)

**Problem:** No pytest or test dependencies in the repo, preventing automated unit testing in CI.

**Fix:** Created `api/requirements-dev.txt`:
```
pytest==7.4.3
pytest-cov==4.1.0
fakeredis==2.21.0
httpx==0.25.2
```

**Rationale:** Separated development dependencies allow lightweight production builds while enabling comprehensive testing in CI.

---

## 16. Worker Requirements Unpinned (worker/requirements.txt)

**Problem:** Same as bug #14.

**Before:**
```
redis
```

**After:**
```
redis==5.0.1
```

**Rationale:** Pinned to match the API version for consistency.

---

## 17. Frontend No package-lock.json (frontend/package.json)

**Problem:** No `package-lock.json` means npm installs vary between environments, causing unreproducible builds.

**Fix:** Ran `npm install` to generate `package-lock.json` and committed it.

**Rationale:** Locked dependencies ensure reproducible Node.js builds; Dockerfiles use `npm ci` (clean install) which requires the lockfile.

---

## Summary

All 17 bugs have been fixed:
- **Environment configuration:** 3 bugs (Redis host/port in api + worker, hardcoded API URL/port in frontend)
- **Health checks:** 3 bugs (missing /health in api, worker, frontend)
- **Reliability & robustness:** 4 bugs (race condition on LPUSH/HSET, missing SIGTERM handler, no connection retry, missing processing state)
- **Data integrity:** 2 bugs (HTTP 200 for missing jobs, bytes-to-string decoding)
- **Dependencies & reproducibility:** 4 bugs (unpinned api/worker/frontend deps, missing test infrastructure)
- **Security:** 1 bug (secret in git history)

The application now containerizes cleanly, runs reliably in Docker Compose, and passes CI/CD gates with linting, testing, security scanning, and integration tests.
