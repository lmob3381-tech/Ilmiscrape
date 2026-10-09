FROM python:3.12-slim

# Install ffmpeg and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 9002

# Command to run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9002"]
