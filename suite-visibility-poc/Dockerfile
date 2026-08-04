FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MONITOR_STATE_FILE=/app/runtime/jenkins_job_state.json \
    MONITOR_STATUS_FILE=/app/runtime/service_status.json \
    SUITE_REPOSITORY_PATH=/suite-repo

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 suite-monitor \
    && mkdir -p /app/runtime \
    && chown -R suite-monitor:suite-monitor /app/runtime

USER suite-monitor

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD ["python", "-m", "suite_visibility.cli", "healthcheck"]

CMD ["python", "-m", "suite_visibility.cli", "serve"]
