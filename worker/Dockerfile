FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade \
        pip==24.3.1 \
        setuptools==75.6.0 \
        wheel==0.45.1

COPY requirements.txt .

RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -M appuser \
    && pip install --no-cache-dir --upgrade \
        pip==24.3.1 \
        setuptools==75.6.0 \
        wheel==0.45.1

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels requirements.txt

COPY worker.py healthcheck.py ./

USER appuser

HEALTHCHECK --interval=5s --timeout=2s --start-period=2s --retries=3 \
    CMD python healthcheck.py || exit 1

CMD ["python", "worker.py"]
