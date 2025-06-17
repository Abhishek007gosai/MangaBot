FROM python:3.10-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Update CA certificates
RUN update-ca-certificates

COPY requirements.txt .

# Replace git+https with git+ssh to avoid authentication issues
RUN sed -i 's|git+https://github.com|git+ssh://git@github.com|' requirements.txt && \
    sed -i '/--use-pep517/d' requirements.txt && \
    python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
