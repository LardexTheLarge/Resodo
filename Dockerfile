FROM python:3.11-slim

# Install wget and Playwright system dependencies
RUN apt-get update && apt-get install -y wget && \
    pip install playwright && \
    playwright install-deps

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy app
COPY . /app
WORKDIR /app

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

