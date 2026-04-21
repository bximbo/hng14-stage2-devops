# Job Processing System — Production Containerized Stack

A microservices job processing system: frontend (Node/Express) → API (FastAPI) → worker (Python) backed by Redis.

## Prerequisites

- **Docker** ≥24 ([install](https://docs.docker.com/install/))
- **Docker Compose** v2+ (bundled with modern Docker Desktop)
- **Git**
- **Ports 3000, 8000 available** (or edit `docker-compose.yml`)

## Quick Start

### 1. Clone and Navigate

```bash
git clone https://github.com/YOUR_USERNAME/hng14-stage2-devops.git
cd hng14-stage2-devops
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local development)
cat .env
```

### 3. Build and Start

```bash
docker compose up -d --build
```

**Expected output:**
```
 ✔ Network jobnet Created
 ✔ Container job_redis Created
 ✔ Container job_api Created
 ✔ Container job_worker Created
 ✔ Container job_frontend Created
```

### 4. Verify Services are Healthy

```bash
docker compose ps
```

All four services should show `healthy` in the STATUS column:
```
NAME                STATUS
job_redis           healthy
job_api             healthy (port 8000)
job_worker          healthy
job_frontend        healthy (port 3000)
```

### 5. Test the Application

Open **http://localhost:3000** in a browser.

- Click **Submit New Job**
- Watch the status update from `queued` → `processing` → `completed`
- Submit multiple jobs; they process in parallel

Or test via curl:

```bash
# Submit a job
JOB_ID=$(curl -s -X POST http://localhost:3000/submit | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# Poll status
curl http://localhost:3000/status/$JOB_ID | jq .

# Repeat until status is "completed"
```

## Architecture

### Services

| Service  | Language | Port | Role |
|----------|----------|------|------|
| redis    | —        | (internal) | Shared message queue & job state store |
| api      | Python/FastAPI | 8000 | REST API: create jobs, fetch status |
| worker   | Python | (internal) | Picks up jobs from queue, processes them |
| frontend | Node/Express | 3000 | Web UI for job submission & tracking |

### Data Flow

1. **Frontend** (`POST /submit`) → **API** creates a job with status "queued" and pushes to Redis queue.
2. **Worker** (`BRPOP "job"`) picks up the job ID, transitions status to "processing", sleeps 2s, marks "completed".
3. **Frontend** (`GET /status/:id`) polls the API until status is "completed".

### Network

All services communicate over a private Docker network `jobnet`:
- Redis is **not exposed** on the host (secure).
- Frontend is the only service with a published port (3000).

## Debugging

### View Logs

```bash
docker compose logs -f api      # Follow API logs
docker compose logs worker      # Worker logs
docker compose logs --all       # All services
```

### Inspect Containers

```bash
docker compose exec api python -c "import redis; print(redis.Redis(host='redis', password=open('.env').read().split('REDIS_PASSWORD=')[1].strip()).ping())"
docker compose exec worker whoami  # Should output "appuser" (non-root)
```

### Reset Redis State

```bash
docker compose down -v          # Remove volumes
docker compose up -d --build    # Rebuild and start fresh
```

## Testing Locally

### Run Unit Tests

```bash
pip install -r api/requirements.txt -r api/requirements-dev.txt
pytest api/tests/ -v --cov=api
```

### Lint Code

```bash
pip install flake8
flake8 api/ worker/

npm install --prefix frontend
npx eslint frontend/

docker run --rm -i hadolint/hadolint < api/Dockerfile
docker run --rm -i hadolint/hadolint < worker/Dockerfile
docker run --rm -i hadolint/hadolint < frontend/Dockerfile
```

## CI/CD Pipeline

GitHub Actions runs on every push to `main` or feature branches:

1. **lint** — flake8 (Python), eslint (JavaScript), hadolint (Dockerfiles)
2. **test** — pytest with coverage; uploads coverage report
3. **build** — builds 3 Docker images, pushes to local registry, exports as artifact
4. **security-scan** — Trivy scans for CRITICAL CVEs; fails if found
5. **integration-test** — spins up full stack in runner, submits a job, polls for completion
6. **deploy** — (main branch only) rolling update with health checks

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for details.

## Production Considerations

- **Secrets:** Use a secrets management tool (e.g., HashiCorp Vault, AWS Secrets Manager) instead of `.env` files.
- **Persistence:** Redis data is ephemeral; add volume persistence for production.
- **Scaling:** Use Kubernetes or a container orchestrator instead of Docker Compose.
- **Monitoring:** Integrate Prometheus metrics and centralized logging (ELK, Datadog).
- **Health Checks:** The Dockerfiles include HEALTHCHECK; configure with appropriate intervals for your environment.

## Documentation

- **[FIXES.md](FIXES.md)** — Detailed list of all bugs found and fixed
- **[.env.example](.env.example)** — Template for environment configuration
- **[docker-compose.yml](docker-compose.yml)** — Full service definitions, networking, resource limits

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 3000 already in use | Change `PORT` in `.env` or `docker-compose.yml` |
| Services stuck "starting" | Check logs: `docker compose logs service_name` |
| Jobs not processing | Verify Redis is healthy: `docker compose exec redis redis-cli ping` |
| Tests fail locally | Ensure `requirements-dev.txt` is installed: `pip install -r api/requirements-dev.txt` |

## Cleanup

```bash
# Stop and remove all containers
docker compose down

# Remove volumes (deletes Redis data)
docker compose down -v

# Remove images
docker compose down -v --rmi all
```

## License

This is an educational project for HNG 2026 Stage 2.
