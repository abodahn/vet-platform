FROM python:3.11-slim

WORKDIR /app

# postgresql-client supplies pg_dump and pg_restore. Without them
# models/backup.py cannot back up a PostgreSQL clinic from inside the
# container — and it correctly refuses rather than reporting a success it
# did not achieve, which would leave the clinic with no backup at all.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p data

EXPOSE 5100

ENV FLASK_ENV=production
ENV DATABASE_PATH=/app/data/platform.db

CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "--timeout", "120", "app:create_app()"]
