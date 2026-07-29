#!/bin/sh
set -eu

alembic upgrade head
python -m server.bootstrap
exec uvicorn server.app:app --host 0.0.0.0 --port 8000
