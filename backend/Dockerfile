FROM python:3.11-slim

# Don't buffer stdout/stderr so logs stream out of the container promptly.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so the layer caches across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Alembic migrations run automatically on startup (see app.main:lifespan); this
# just serves the API. Bind to 0.0.0.0 so the port is reachable from the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
