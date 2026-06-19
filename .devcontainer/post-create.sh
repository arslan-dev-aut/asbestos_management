#!/usr/bin/env bash
set -e

echo "==> Installing dev tools..."
pip install --no-cache-dir pytest ruff

echo "==> Installing backend dependencies..."
cd /workspace/backend
pip install --no-cache-dir -r requirements.txt

echo "==> Installing frontend dependencies..."
cd /workspace/frontend
npm install

echo ""
echo "==> Dev container setup complete!"
echo "    Backend:  cd backend && uvicorn main:app --reload --port 8000"
echo "    Frontend: cd frontend && npm run dev"
