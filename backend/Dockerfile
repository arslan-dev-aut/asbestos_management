# B6 Asbestos Management — backend image.
# Built with docker-compose context ./backend (build context root == backend/).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps: build essentials for any wheels that need compiling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies first for layer caching.
COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the backend package into /app/backend so `import backend...` resolves.
COPY . /app/backend/

EXPOSE 8000

# Schema is managed in Azure (tables pre-created); no migration step at boot.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
