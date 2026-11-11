FROM python:3.14.8-slim-trixie AS builder

WORKDIR /build
COPY requirements.txt _download_model.py ./

RUN pip install --no-cache-dir --root-user-action=ignore \
    -c requirements.txt huggingface_hub==2.2.0 tokenizers && \
    python _download_model.py && \
    rm _download_model.py

FROM python:3.14.8-slim-trixie

COPY --from=builder /model /model

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Nothing installs packages at runtime, so pip only adds CVEs.
RUN pip install --no-cache-dir --root-user-action=ignore --no-deps \
    -r requirements.txt && \
    pip uninstall -y --root-user-action=ignore pip && \
    rm -rf /root/.cache

COPY app.py .
# --no-deps can't catch a missing dependency, so fail the build instead of startup.
RUN python -B -c "import app"

EXPOSE 80
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
