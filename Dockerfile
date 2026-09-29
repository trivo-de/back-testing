FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
RUN python -m pip install --no-cache-dir .

COPY migrations/ migrations/
COPY scripts/ scripts/
COPY docs/data/vn30f1m/runtime-policy*.json docs/data/vn30f1m/

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data/backtest-store \
    && chown -R app:app /app/data
USER app

EXPOSE 8000

CMD ["sh", "-c", "if [ \"$BACKTEST_LEGACY_BACKEND\" = \"postgres\" ]; then python scripts/apply_migrations.py || exit 1; fi; exec python -m uvicorn backtest_hpg.main:app --host 0.0.0.0 --port 8000"]
