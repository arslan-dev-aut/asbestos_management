FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install Microsoft ODBC Driver 18 (required for joblogic-db read-only replica via aioodbc)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Playwright browsers and dependencies (for Playwright & Puppeteer MCP servers)
RUN npx -y playwright@latest install --with-deps chromium

# Install common dev tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set default shell to bash
ENV SHELL=/bin/bash
