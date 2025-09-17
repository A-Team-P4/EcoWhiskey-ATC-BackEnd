FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user to run the service
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose the application port
EXPOSE 8000

# Default command to run the FastAPI application with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
