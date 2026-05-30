FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# Optional: Playwright/Crawl nicht im Standard-Image
# RUN pip install -e ".[playwright,crawl]" && playwright install chromium

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["bot"]
