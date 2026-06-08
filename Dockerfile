# Use a slim Python image
FROM python:3.11-slim

# Install system dependencies: poppler and tesseract
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY document_reader.py .

# Expose the port Render will provide (default 5000)
ENV PORT=5000

# Run with gunicorn
CMD gunicorn document_reader:app --bind 0.0.0.0:$PORT
