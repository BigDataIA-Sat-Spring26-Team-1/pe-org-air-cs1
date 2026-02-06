# Dockerfile for PE Org-AI-R Platform
FROM python:3.11-slim-bookworm

# Set working directory inside container
WORKDIR /app

# Set Playwright browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

# Install required system-level dependencies for browsers and networking
# We include fonts and libraries manually to ensure compatibility with ARM64/Debian Bookworm
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    fonts-liberation \
    fonts-unifont \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Installing Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
# We skip 'install-deps' because we already installed the required libs above
RUN playwright install chromium

# Copy application source code and tests
COPY app/ ./app/
COPY tests/ ./tests/

# Create and switch to a non-root user for security
RUN useradd -m appuser && \
    mkdir -p /ms-playwright && \
    chown -R appuser:appuser /app /ms-playwright
USER appuser


# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
