FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY src ./src
COPY crawlers ./crawlers
COPY agent ./agent
COPY tools ./tools
COPY templates ./templates
COPY config.py ./config.py
COPY scripts ./scripts
RUN chmod +x ./scripts/docker-entrypoint.sh

EXPOSE 8000
CMD ["/app/scripts/docker-entrypoint.sh"]
