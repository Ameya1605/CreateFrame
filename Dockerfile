FROM python:3.11

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API source code
COPY apps/api/ ./apps/api/

# Hugging Face Spaces runs on port 7860 by default
ENV PORT=7860
EXPOSE 7860

# Navigate to the api directory and start uvicorn
CMD ["sh", "-c", "cd apps/api && uvicorn main:app --host 0.0.0.0 --port 7860"]
