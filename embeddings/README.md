# Baserow Embeddings Service

A lightweight, self-contained text embedding microservice for Baserow's AI Assistant features. This service provides fast sentence embeddings using an ONNX-optimized model.

## Overview

This service converts text into dense vector representations (embeddings) that can be used for:

-   Semantic search and similarity matching
-   Document retrieval for RAG (Retrieval-Augmented Generation)
-   Finding relevant database rows based on natural language queries
-   Clustering and classification tasks

## Model

**Model**: `sentence-transformers/all-MiniLM-L6-v2`

-   Embedding dimension: 384
-   Optimized for semantic similarity tasks
-   Converted to ONNX format for faster inference
-   Compact size with good performance trade-off

## Architecture

The service uses a multi-stage Docker build:

1. **Builder stage**: Downloads the model and converts it to ONNX format
2. **Runtime stage**: Minimal Python image with only runtime dependencies
3. **Result**: Small, production-ready container (~500MB)

### Key Features

-   **ONNX Runtime**: 2-3x faster inference compared to PyTorch
-   **Mean pooling**: Converts token embeddings to sentence embeddings
-   **L2 normalization**: Enables cosine similarity via dot product
-   **Batch support**: Process multiple texts in a single request
-   **Health checks**: Built-in health endpoint for monitoring

## Docker

### Run locally

```
docker run -p 8080:80 baserow/embeddings:1.0.0
```

### Build for publish

```
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t baserow/embeddings:1.0.0 \
  -t baserow/embeddings:latest \
  --push .
```

## API

### Endpoints

#### `POST http://localhost:8080/embed`

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

## Building

```bash
docker build -t baserow-embeddings .
```

## Running

```bash
docker run -p 8080:80 baserow-embeddings
```

The service will be available at `http://localhost:8080`.

## Development

### Local Testing

```bash
# Install dependencies
pip install optimum[onnxruntime]==1.27.0 transformers==4.53.0 starlette==0.48.0 uvicorn==0.37.0

# Download model
python -c "
from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer
model = ORTModelForFeatureExtraction.from_pretrained('sentence-transformers/all-MiniLM-L6-v2', export=True)
tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
model.save_pretrained('./model')
tokenizer.save_pretrained('./model')
"

# Run locally
uvicorn app:app --host 0.0.0.0 --port 8080
```

### Testing the API

```python
import requests

response = requests.post('http://localhost:8080/embed', json={
    'text': ['Hello world', 'How are you?']
})

embeddings = response.json()['embeddings']
print(f"Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}")
```

## Integration with Baserow

This service is used by Baserow's AI Assistant to:

1. **Index database content**: Convert rows into searchable embeddings
2. **Semantic search**: Find relevant rows based on user questions
3. **Context retrieval**: Provide relevant data to the LLM for answering questions

The embeddings enable the assistant to understand the semantic meaning of user queries and match them with the most relevant database records, even when there's no exact keyword match.

## Performance

-   **Inference time**: ~10-30ms per text on CPU
-   **Batch processing**: More efficient for multiple texts
-   **Memory usage**: ~200MB RAM
-   **Throughput**: ~100-300 requests/second (CPU-dependent)

## Dependencies

-   Python 3.13
-   optimum[onnxruntime] 1.27.0
-   transformers 4.53.0
-   starlette 0.48.0
-   uvicorn 0.37.0

## License

This service is part of the Baserow project. See the main repository for license information.
