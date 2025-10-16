# --- Stage 1: Builder ---
FROM python:3.13-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VENV_PATH=/opt/venv
RUN python3 -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv

COPY requirements.txt .
# Force CPU version of torch to avoid CUDA dependencies and then install other dependencies
RUN uv pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --no-cache -r requirements.txt

# Download the embedding model and store it in /model
COPY _download_model.py /tmp/download_model.py
RUN python /tmp/download_model.py && rm /tmp/download_model.py


# --- Stage 2: Final Image ---
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv
ENV PATH="$VENV_PATH/bin:$PATH"

# Running as a non-root user for better security
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appgroup ${VENV_PATH} ${VENV_PATH}
COPY --from=builder --chown=appuser:appgroup /model /model
COPY --chown=appuser:appgroup app.py .

USER appuser
EXPOSE 80

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]