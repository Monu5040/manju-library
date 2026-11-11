"""Container health check: GET /api/health/ on the local Gunicorn. Exit 0 when healthy."""

import os
import sys
import urllib.request

# Django only answers to configured host names, so send the first one.
host = os.environ.get("ALLOWED_HOSTS", "localhost").split(",")[0].strip()
request = urllib.request.Request(
    "http://127.0.0.1:8000/api/health/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
try:
    with urllib.request.urlopen(request, timeout=4) as response:  # noqa: S310 (fixed local URL)
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
