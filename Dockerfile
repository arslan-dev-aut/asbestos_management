# syntax=docker/dockerfile:1.6
# Unified Dockerfile — three targets: `backend`, `frontend`, `standalone`.
# Build each via: docker build --target <backend|frontend|standalone> .

# ─── Backend ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS backend

# Install Azure CLI so DefaultAzureCredential can use host az login tokens
# (docker-compose mounts %USERPROFILE%/.azure into the container at /root/.azure)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]

# ─── Frontend build stage ────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .

# Build with placeholder values - these get substituted at runtime by entrypoint script
ENV VITE_API_URL=VITE_API_URL_PLACEHOLDER
ENV VITE_BASE_IDENTITY=VITE_BASE_IDENTITY_PLACEHOLDER
ENV VITE_BASE_CLIENT_ID=VITE_BASE_CLIENT_ID_PLACEHOLDER

RUN npm run build

# ─── Frontend serve stage ────────────────────────────────────────────────────
FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template

EXPOSE 80
# At startup: read the container's DNS nameserver from /etc/resolv.conf and
# substitute both NGINX_RESOLVER and BACKEND_UPSTREAM into the nginx config.
CMD ["/bin/sh", "-c", \
  "export NGINX_RESOLVER=$(awk 'BEGIN{ORS=\" \"} $1==\"nameserver\" {print $2; exit}' /etc/resolv.conf); \
   envsubst '${NGINX_RESOLVER} ${BACKEND_UPSTREAM}' \
     < /etc/nginx/conf.d/default.conf.template \
     > /etc/nginx/conf.d/default.conf && \
   nginx -g 'daemon off;'"]

# ─── Standalone (single container: backend + frontend) ───────────────────────
FROM python:3.12-slim AS standalone

# Install nginx, supervisor, and Azure CLI (so DefaultAzureCredential can use
# host az login tokens — docker-compose mounts %USERPROFILE%/.azure into the
# container at /root/.azure).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        gettext-base \
        curl \
        ca-certificates \
        apt-transport-https \
        gnupg \
        lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Remove default nginx site
RUN rm -f /etc/nginx/sites-enabled/default

# Backend: install Python deps and copy code
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

# Frontend: copy pre-built static assets from the build stage
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Nginx config template (same as the frontend target)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template

# Supervisord config
COPY supervisord.conf /etc/supervisord.conf

# Entrypoint script
COPY entrypoint-standalone.sh /app/entrypoint-standalone.sh
RUN chmod +x /app/entrypoint-standalone.sh

EXPOSE 80

CMD ["/app/entrypoint-standalone.sh"]
