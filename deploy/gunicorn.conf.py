"""Gunicorn settings for the container. Values can be tuned with environment variables."""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 20
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
worker_tmp_dir = "/dev/shm"
# Gunicorn 27 opens a control socket under $HOME/.gunicorn by default; the root filesystem
# is read-only and gunicornc is not used, so the control interface stays off.
control_socket_disable = True

# Access lines contain full paths, including one-time confirmation and withdrawal
# tokens. Caddy writes the access log with those segments redacted instead.
accesslog = None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Scheme comes from Django's SECURE_PROXY_SSL_HEADER; Gunicorn trusts no forwarders.
forwarded_allow_ips = ""
limit_request_line = 4094
limit_request_fields = 100
