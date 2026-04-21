FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN useradd -u 10001 -M appuser

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .

RUN pip install --no-cache --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

COPY worker.py healthcheck.py .

USER appuser

HEALTHCHECK --interval=5s --timeout=2s --start-period=2s --retries=3 \
    CMD python healthcheck.py || exit 1

CMD ["python", "worker.py"]
