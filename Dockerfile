# Use official Python image from Docker Hub
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first (layer caching optimization)
# This way, if only code changes, Docker uses cached dependencies
COPY requirements.txt requirements.txt

# Install Python dependencies
# --no-cache-dir saves space in container
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project into container
COPY . .

# Create directories for audio and events (if they don't exist)
RUN mkdir -p audio_output events

# Expose port 5000
# (doesn't publish to host, just documents that app uses 5000)
EXPOSE 5000

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check - Docker monitors if app is healthy
# Checks every 30s if endpoint responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/').read()" || exit 1

# Command to run when container starts
# gunicorn = production WSGI server (better than Flask dev server)
# --bind 0.0.0.0:5000 = listen on all interfaces, port 5000
# --workers 4 = 4 worker processes (handle concurrent requests)
# --timeout 120 = request timeout 120s (for long TTS generation)
# backend:app = import backend.py, use app object
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "backend:app"]
