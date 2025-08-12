# Stage 1: Build the frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app

# Copy frontend package files
COPY frontend/package*.json ./
COPY frontend/bun.lockb ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/ .

# Add before RUN npm run build
ARG VITE_API_BASE_URL=https://arunachalasamudra.co.in/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build the frontend
RUN npm run build

# Stage 2: Build the final backend image with frontend
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Install uv from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies required by your application
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Set the working directory
WORKDIR /app

# Copy backend dependency definitions
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies into the virtual environment
RUN uv sync --no-cache --frozen

# Copy backend application code
COPY backend/alembic.ini .
COPY backend/alembic ./alembic
COPY backend/src ./src

# Copy the built frontend from the first stage
COPY --from=frontend-builder /app/dist ./src/ui

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the application will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.server:get_app", "--host", "0.0.0.0", "--port", "8000", "--factory"] 