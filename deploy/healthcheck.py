"""Container health check: GET /healthz/ on Gunicorn with the public Host header."""

import os
import sys
import urllib.request

host = (os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")[0] or "localhost").strip()
request = urllib.request.Request("http://127.0.0.1:8000/healthz/", headers={"Host": host})
try:
    with urllib.request.urlopen(request, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
