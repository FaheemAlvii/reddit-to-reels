# Reddit Video Engine
# Author: Faheem Alvi <faheemalvi2000@gmail.com>
# GitHub: https://github.com/FaheemAlvii

# Stage 1: build the React frontend
FROM node:20-alpine AS frontend

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .
RUN pnpm build

# Stage 2: Python runtime with FFmpeg
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY --from=frontend /app/dist ./dist

# Default config and channels are mounted as volumes; create empty placeholders
RUN mkdir -p posts videos backgrounds audio

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "8000"]
