# Start from a lightweight Python image
FROM python:3.12-slim

# Keep Python output unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal build tools for wheels (kept small)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install the uv package manager
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir uv

# Copy only the files needed to run the app (avoid copying a local venv)
COPY pyproject.toml uv.lock shell_server.py README.md /app/

# If you want to pre-install dependencies with uv (optional), you can try:
# RUN uv install || true
# We skip a hard install step because different uv versions may expose different commands.

# Default command uses the same invocation you use locally
CMD ["uv", "run", "shell_server.py"]
