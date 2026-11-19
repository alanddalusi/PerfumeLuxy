# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_ENV=production

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/staticfiles /app/media /srv/catalog_assets \
    && chown app:app /app/staticfiles /app/media /srv/catalog_assets

# Code stays owned by root: the app user can read it but not modify it.
COPY . .
RUN sed -i 's/\r$//' deploy/entrypoint.sh deploy/backup/*.sh && chmod 0755 deploy/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["deploy/entrypoint.sh"]
CMD ["serve"]
