#!/usr/bin/env python
import os
import sys

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

try:
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    r.ping()
    sys.exit(0)
except Exception as e:
    print(f"Healthcheck failed: {e}")
    sys.exit(1)
