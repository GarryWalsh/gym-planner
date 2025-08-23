#!/usr/bin/env bash
# Simple launcher for the Streamlit app
# Usage: ./scripts/run_app.sh [host] [port] [--headless]

HOST="${1:-127.0.0.1}"
PORT="${2:-8501}"
HEADLESS_FLAG=""
if [[ "$3" == "--headless" ]]; then
  HEADLESS_FLAG="--server.headless true"
fi

python -m streamlit run app/streamlit_app.py --server.address "$HOST" --server.port "$PORT" $HEADLESS_FLAG
