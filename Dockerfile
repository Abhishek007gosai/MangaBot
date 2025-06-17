# ... previous Dockerfile content ...

# Install pip requirements
COPY requirements.txt .

# Fixed installation command
RUN sed -i '/--use-pep517/d' requirements.txt && \
    python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

# ... rest of Dockerfile ...
