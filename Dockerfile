# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Fix for setuptools version metadata issue
ENV SETUPTOOLS_USE_DISTUTILS=stdlib

WORKDIR /app

# Upgrade build tools to fix version metadata issue
RUN python -m pip install --upgrade "pip==24.0" "setuptools==68.2.2" "wheel==0.42.0"

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN alembic upgrade head

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["bash", "start.sh"]
