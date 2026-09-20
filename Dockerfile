FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
RUN python -m pip install --no-cache-dir .

COPY migrations/ migrations/
COPY scripts/ scripts/

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

CMD ["sh", "-c", "python scripts/apply_migrations.py && exec python -m uvicorn backtest_hpg.main:app --host 0.0.0.0 --port 8000"]
