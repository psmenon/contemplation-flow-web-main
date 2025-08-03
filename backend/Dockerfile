# This stage creates the final, lean production image.
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

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies into the virtual environment
RUN uv sync --no-cache --frozen

# Copy application code
COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the application will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.server:get_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
