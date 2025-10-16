FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY _download_model.py .

RUN pip install --no-cache-dir \
    huggingface_hub==0.31.0 \
    transformers==4.53.0 && \
    python _download_model.py && \
    rm _download_model.py

FROM python:3.11-slim-bookworm

COPY --from=builder /model /model

RUN pip install --no-cache-dir \
    onnxruntime==1.20.1 \
    transformers==4.53.0 \
    starlette==0.48.0 \
    uvicorn==0.37.0 && \
    rm -rf /root/.cache

WORKDIR /app
COPY app.py .

EXPOSE 80
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
