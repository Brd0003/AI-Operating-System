FROM python:3.11-slim

WORKDIR /app/src

# Set high-timeout thresholds for thick packages
ENV PIP_DEFAULT_TIMEOUT=150
ENV PIP_RETRIES=5

# Bake PYTHONPATH into the image so bare `docker run` works without compose env
ENV PYTHONPATH=/app/src

COPY requirements.txt /app/src/requirements.txt

# Run the install sequence utilizing standard public and cached fallbacks natively
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

EXPOSE 10001
ENTRYPOINT ["python", "harness.py"]
