# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    WEB_CONCURRENCY=3

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
# Copied files keep the server checkout's permissions. Hardened servers (umask 027) leave
# them unreadable to other users, so open them up for the unprivileged app user below.
RUN chmod -R a+rX /app

# Static files for the Django admin back office, served by WhiteNoise.
RUN ENVIRONMENT=build python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "healthcheck.py"]

# Workers come from WEB_CONCURRENCY.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "60", "--access-logfile", "-"]
