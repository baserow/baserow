from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import onnxruntime as ort
from tokenizers import Tokenizer
import numpy as np
import json
import os

# Load ONNX model directly
MODEL_DIR = "/model"
tokenizer = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
with open(os.path.join(MODEL_DIR, "tokenizer_config.json")) as f:
    tokenizer_config = json.load(f)
# Match transformers' padding=True/truncation=True, not the 128-token defaults in tokenizer.json.
tokenizer.enable_truncation(max_length=tokenizer_config["model_max_length"])
tokenizer.enable_padding(
    pad_id=tokenizer.token_to_id(tokenizer_config["pad_token"]),
    pad_token=tokenizer_config["pad_token"],
)

# Create inference session
model_path = os.path.join(MODEL_DIR, "model.onnx")
session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

def mean_pooling(token_embeddings, attention_mask):
    input_mask_expanded = np.expand_dims(attention_mask, -1)
    input_mask_expanded = np.broadcast_to(input_mask_expanded, token_embeddings.shape).astype(float)
    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask

async def embed(request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if not data or "texts" not in data:
        return JSONResponse({"error": "Missing texts field"}, status_code=400)

    texts = data["texts"]
    if isinstance(texts, str):
        texts = [texts]

    encodings = tokenizer.encode_batch(texts)
    encoded = {
        "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
    }
    ort_inputs = {k: v for k, v in encoded.items()}

    # Run model
    ort_outputs = session.run(None, ort_inputs)
    token_embeddings = ort_outputs[0]

    embeddings = mean_pooling(token_embeddings, encoded["attention_mask"])
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
