FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    optimum[onnxruntime]==1.27.0 \
    transformers==4.53.0

COPY _download_model.py /tmp/download_model.py
RUN python /tmp/download_model.py && rm /tmp/download_model.py

FROM python:3.13-slim

RUN pip install --no-cache-dir \
    optimum[onnxruntime]==1.27.0 \
    transformers==4.53.0 \
    starlette==0.48.0 \
    uvicorn==0.37.0 \
    && rm -rf /root/.cache

COPY --from=builder /model /model

COPY app.py /app/app.py

WORKDIR /app

EXPOSE 80

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]