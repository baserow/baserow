from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer
import numpy as np

# Load ONNX model and tokenizer once at startup
model = ORTModelForFeatureExtraction.from_pretrained("/model")
tokenizer = AutoTokenizer.from_pretrained("/model")


def mean_pooling(token_embeddings, attention_mask):
    """Mean pooling to get sentence embeddings"""
    input_mask_expanded = np.expand_dims(attention_mask, -1)
    input_mask_expanded = np.broadcast_to(
        input_mask_expanded, token_embeddings.shape
    ).astype(float)

    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)

    return sum_embeddings / sum_mask


async def embed(request):
    try:
        data = await request.json()
    except:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if not data or "texts" not in data:
        return JSONResponse({"error": "Missing texts field"}, status_code=400)

    texts = data["texts"]

    if isinstance(texts, str):
        texts = [texts]

    encoded = tokenizer(texts, padding=True, truncation=True, return_tensors="np")
    outputs = model(**encoded)
    embeddings = mean_pooling(outputs.last_hidden_state, encoded["attention_mask"])

    # Normalize embeddings
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    return JSONResponse({"embeddings": embeddings.tolist()})


async def health(request):
    return JSONResponse({"status": "healthy"})


app = Starlette(
    routes=[
        Route("/embed", embed, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ]
)
