#!/usr/bin/env python
"""Container health check: web answers /health/live; worker has a fresh heartbeat file."""

import os
import sys
import time
import urllib.request
from pathlib import Path

role = Path("/tmp/hd-role").read_text().strip() if Path("/tmp/hd-role").exists() else "web"  # noqa: S108  # nosec B108 - container-private /tmp

if role in {"web", "dev"}:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=4) as resp:  # noqa: S310  # nosec B310 - fixed local URL
            sys.exit(0 if resp.status == 200 else 1)
    except Exception:  # noqa: BLE001
        sys.exit(1)
elif role == "worker":
    heartbeat = Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/hd-heartbeat"))  # noqa: S108  # nosec B108 - container-private /tmp
    sys.exit(0 if heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 90 else 1)
sys.exit(0)
