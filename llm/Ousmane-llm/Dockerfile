FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RESULTS_DIR=/app/data/results

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/data/results \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "ousmane_llm.api:app", "--host", "0.0.0.0", "--port", "8000"]
