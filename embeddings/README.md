# Baserow Embeddings Service

A lightweight, self-contained text embedding microservice for Baserow's AI Assistant features. This service provides fast sentence embeddings using an ONNX export of the model.

## Overview

This service converts text into dense vector representations (embeddings) that can be used for:

-   Semantic search and similarity matching
-   Document retrieval for RAG (Retrieval-Augmented Generation)
-   Clustering and classification tasks

## Model

**Model**: `sentence-transformers/all-MiniLM-L6-v2`, from its ONNX export `optimum/all-MiniLM-L6-v2` at a pinned revision

-   Embedding dimension: 384
-   Texts are truncated at 512 tokens. Baserow's stored vectors were made this way, so changing the truncation or the model means re-embedding them.
-   Optimized for semantic similarity tasks
-   Compact size with good performance trade-off

## Architecture

The service uses a multi-stage Docker build:

1. **Builder stage**: Downloads the ONNX model and configures its tokenizer
2. **Runtime stage**: Minimal Python image with only runtime dependencies
3. **Result**: Small, production-ready container (~380MB)

### Key Features

-   **ONNX Runtime**: CPU inference without PyTorch
-   **Mean pooling**: Converts token embeddings to sentence embeddings
-   **L2 normalization**: Enables cosine similarity via dot product
-   **Batch support**: Process multiple texts in a single request
-   **Health checks**: Built-in health endpoint for monitoring

## Docker

There are two images. Both create the same vectors, so they can be swapped without re-embedding.

| Image                          | Runs on               | Platforms                    | Size    |
| ------------------------------ | --------------------- | ---------------------------- | ------- |
| `baserow/embeddings:1.1.0`     | CPU                   | `linux/amd64`, `linux/arm64` | ~0.6 GB |
| `baserow/embeddings:1.1.0-gpu` | NVIDIA GPU, with CUDA | `linux/amd64`                | ~2.2 GB |

The CPU image is enough for the AI assistant's knowledge base and for searching. The GPU image is only worth it to embed large volumes, like enabling semantic search on big tables.

### Run the CPU image

```bash
docker run -p 127.0.0.1:8080:80 baserow/embeddings:1.1.0
```

The service will be available at `http://localhost:8080`.

### Run the GPU image

The host needs an NVIDIA driver of version 525 or newer and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

```bash
docker run --gpus all -p 127.0.0.1:8080:80 baserow/embeddings:1.1.0-gpu
```

-   It fails to start when no GPU is usable, instead of silently falling back to the CPU. Set `EMBEDDINGS_DEVICE=cpu` to run it without a GPU anyway.
-   It processes 64 texts at a time instead of 8, because a GPU only runs at full speed with bigger batches. Set `BASEROW_EMBEDDINGS_TEXTS_PER_REQUEST` to 64 in Baserow, so that its requests fill those batches.
-   Requests are processed one at a time, while the CPU handles tokenization and JSON. Run two to four containers on one GPU to keep it busy. On an NVIDIA RTX A4000, four containers embedded about 1,200 texts of 200 to 1,000 characters per second, against 18 per second for the CPU image with 1 CPU.
-   Its vectors differ from the CPU image's only in the last decimals, which doesn't noticeably change cosine distances.

### Build and publish

Bump the version in the tags, and in the run commands above, for every release. Publish both images with the same version.

CPU image:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t baserow/embeddings:1.1.0 \
  -t baserow/embeddings:latest \
  --push .
```

GPU image, which only supports `linux/amd64`:

```bash
docker buildx build \
  --platform linux/amd64 \
  --build-arg REQUIREMENTS=requirements-gpu.txt \
  -t baserow/embeddings:1.1.0-gpu \
  -t baserow/embeddings:latest-gpu \
  --push .
```

### Build and run from source

CPU image:

```bash
docker build -t baserow-embeddings .
docker run -p 127.0.0.1:8080:80 baserow-embeddings
```

GPU image:

```bash
docker build --build-arg REQUIREMENTS=requirements-gpu.txt -t baserow-embeddings-gpu .
docker run --gpus all -p 127.0.0.1:8080:80 baserow-embeddings-gpu
```

### Configuration

| Environment variable     | Description                                                                                                               | Default                                                            |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `EMBEDDINGS_NUM_THREADS` | Number of CPU threads used for inference, as a positive integer. Requests are processed one at a time, using all threads. | The container's CPU limit rounded up, or all CPUs without a limit. |
| `EMBEDDINGS_MODEL_DIR`   | Directory with the model files. Change it only to run the service outside Docker.                                         | `/model`                                                           |
| `EMBEDDINGS_DEVICE`      | `cpu` or `gpu`. Set `cpu` to run the GPU image without a GPU.                                                             | `gpu` in the GPU image, otherwise `cpu`.                           |

## API

### Endpoints

#### `POST /embed`

Generate embeddings for one or more texts.

**Request:**

```json
{
    "texts": "Your text here"
}
```

or for batching:

```json
{
    "texts": ["First text", "Second text", "Third text"]
}
```

**Response:**

```json
{
  "embeddings": [[0.123, -0.456, ...], ...]
}
```

Texts longer than 512 tokens are truncated.

**Errors:** `400` with an `error` message for invalid JSON, a missing `texts` field, a `texts` that isn't a string or a list of strings, an empty list or more than 256 texts, and `413` for a body over 1 MiB.

**Example:**

```bash
curl -X POST http://localhost:8080/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": "What is the capital of France?"}'
```

#### `GET /health`

Health check endpoint.

**Response:**

```json
{
    "status": "healthy"
}
```

## Development

### Local Testing

```bash
# From this directory, with Python 3.13 or newer (the image uses 3.14)
python3 -m venv .venv
source .venv/bin/activate

# Install the image's packages, plus huggingface_hub to download the model
pip install --no-deps -r requirements.txt
pip install -c requirements.txt huggingface_hub==2.2.0

# Download model
export EMBEDDINGS_MODEL_DIR="$PWD/model"
python _download_model.py

# Run locally, in a shell where EMBEDDINGS_MODEL_DIR is set
uvicorn app:app --host 127.0.0.1 --port 8080
```

### Testing the API

```python
import json
import urllib.request

request = urllib.request.Request(
    "http://localhost:8080/embed",
    data=json.dumps({"texts": ["Hello world", "How are you?"]}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    embeddings = json.load(response)["embeddings"]

print(f"Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}")
```

## Integration with Baserow

Baserow's AI Assistant uses this service to search the Baserow documentation:

1. **Indexing**: after migrations, or on demand with the `sync_knowledge_base` management command, Baserow splits the docs into chunks and stores their embeddings
2. **Search**: the assistant's `search_user_docs` tool embeds the user's question and finds the closest chunks, even without a keyword match
3. **Context**: the matching chunks are passed to the LLM to answer the question

## Performance

Measured on an Apple M2 Max with the Helm chart's limits of 1 CPU and 1.5 GiB:

-   **Inference time**: about 6 ms for a short query and 75 ms for a 1,000-character text
-   **Batch processing**: saves HTTP round trips, not CPU time. Each group of 8 texts is padded to its longest text, so mixing short and long texts costs extra CPU, about 50% more for 1,000-character docs chunks.
-   **Memory usage**: about 150 MB idle, about 450 MB with 1,000-character texts and up to about 700 MB with texts at the 512-token limit, because requests are processed 8 texts at a time
-   **Throughput**: about 150 short queries or 12 texts of 1,000 characters per second. Long texts scale with more CPUs, short queries much less.

## Dependencies

Python 3.14, with every runtime package pinned in [requirements.txt](requirements.txt), so rebuilds install exactly the same versions. `huggingface_hub` is only used in the build stage, to download the model.

To update a package, install the new versions of `numpy`, `onnxruntime`, `starlette` and `uvicorn` into a clean Python 3.14 environment, add `tokenizers` with `--no-deps`, and write the output of `pip freeze` below the comment at the top of `requirements.txt`. The build stage installs `huggingface_hub`, pinned in the Dockerfile and above, with `-c requirements.txt`, so check that it still installs. After a bump, compare a few vectors with the previous image.

[requirements-gpu.txt](requirements-gpu.txt) pins the GPU image the same way, with `onnxruntime-gpu[cuda,cudnn]` instead of `onnxruntime`, in a `linux/amd64` environment. Keep `onnxruntime-gpu` at the same version as `onnxruntime`.

## License

This service is part of the Baserow project. See the main repository for license information.
