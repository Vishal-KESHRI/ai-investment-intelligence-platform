#!/usr/bin/env bash
# Boot the full stack inside one Hugging Face Space container.
set -e
cd /home/user/app
mkdir -p data

# 1) Backend (internal). Seeds the SQLite DB on first startup.
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# 2) Wait for the backend to be healthy before exposing the UI.
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "backend ready"; break
  fi
  sleep 1
done

# 3) Dashboard (public port 7860, behind the HF proxy).
exec streamlit run dashboard/app.py \
  --server.port 7860 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
