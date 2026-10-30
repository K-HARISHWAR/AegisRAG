#!/bin/bash
set -e

echo "===================================================="
echo "    AegisRAG Enterprise Assistant - Backend Startup "
echo "===================================================="

# Check and wait for PostgreSQL if configured
if [[ "${DATABASE_URL:-}" == *"postgres"* ]]; then
  echo "[INFO] Waiting for PostgreSQL database connection..."
  python - << 'EOF'
import asyncio
import os
import sys
import time
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def wait_for_db():
    db_url = os.environ.get("DATABASE_URL", "")
    max_retries = 30
    delay = 1
    for attempt in range(1, max_retries + 1):
        try:
            engine = create_async_engine(db_url, pool_pre_ping=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            print(f"[INFO] Successfully connected to PostgreSQL (attempt {attempt}).")
            return True
        except Exception as err:
            if attempt == max_retries:
                print(f"[ERROR] Database connection failed after {max_retries} attempts: {err}", file=sys.stderr)
                return False
            time.sleep(delay)
    return False

if not asyncio.run(wait_for_db()):
    sys.exit(1)
EOF
fi

# Ensure storage and Chroma directories exist
mkdir -p "${LOCAL_STORAGE_DIR:-/app/data/uploads}"
mkdir -p "${CHROMA_PERSIST_DIRECTORY:-/app/data/chroma}"

# Apply Alembic schema migrations
echo "[INFO] Running database migrations with Alembic..."
alembic upgrade head || {
  echo "[WARN] Alembic upgrade head exited with status $?. Continuing..."
}

# Optional seed step
if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
  echo "[INFO] SEED_ON_STARTUP=true: Seeding benchmark documents and ChromaDB index..."
  python -m evals.seed_eval_corpus || python -m app.db.seed || echo "[WARN] Seeding encountered an error, continuing startup."
fi

# Launch Uvicorn
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-1}"

echo "[INFO] Starting Uvicorn on ${HOST}:${PORT} (workers=${WORKERS})..."
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --workers "${WORKERS}"
