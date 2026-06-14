FROM python:3.11-slim

# Set environment variables for non-interactive install and cloud mode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLOUD_MODE=1

# Install system dependencies (ca-certificates, gnupg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set working directory
RUN useradd -m appuser
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Switch to non-root user
USER appuser

# Expose Flask port
EXPOSE 8080

# Run Flask app with gunicorn
# Set default port for Cloud Run
ENV PORT=8080
# Run Flask app with gunicorn binding to the PORT env var
CMD gunicorn -b 0.0.0.0:${PORT} app:app
