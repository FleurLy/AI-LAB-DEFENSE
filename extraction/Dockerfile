FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmagic1 \
        libzbar0 \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY .env.example README.md ./
RUN mkdir -p /app/data/raw /app/data/attachments /app/data/work /app/data/normalized

EXPOSE 1025
CMD ["python", "-m", "email_pipeline.main"]

