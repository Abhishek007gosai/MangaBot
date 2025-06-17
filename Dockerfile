# Add this at the VERY TOP of your Dockerfile (new line)
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install pip requirements
COPY requirements.txt .

# Fixed installation command (your existing fix)
RUN sed -i '/--use-pep517/d' requirements.txt && \
    python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

# Add your CMD or ENTRYPOINT here
CMD ["python", "main.py"]
