import asyncio
import json
import math
import os
import threading

import numpy as np
import onnxruntime as ort
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from tokenizers import Tokenizer

MODEL_DIR = os.environ.get("EMBEDDINGS_MODEL_DIR", "/model")
# onnxruntime keeps the memory of its largest batch, so cap the batch size.
INFERENCE_BATCH_SIZE = 8
# The tokenizer reads whole texts before truncating them, so bound the input.
MAX_BODY_BYTES = 2**20
# Each text adds about 8 KB of JSON to the response.
MAX_TEXTS = 256

tokenizer = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
# A raw download truncates at 128 tokens, while the stored vectors used 512.
if not tokenizer.truncation or tokenizer.truncation["max_length"] != 512:
    raise RuntimeError(f"Run _download_model.py to configure {MODEL_DIR}")


def read_cgroup_cpu_quota() -> tuple[int, int] | None:
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            quota, period = f.read().split()
        return None if quota == "max" else (int(quota), int(period))
    except (OSError, ValueError):
        pass

    # Older hosts still run cgroup v1, where -1 means unlimited.
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
            quota = int(f.read())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
            period = int(f.read())
        return None if quota <= 0 else (quota, period)
    except (OSError, ValueError):
        return None


def default_num_threads() -> int:
    # onnxruntime ignores the container CPU limit and would get throttled.
    count = os.process_cpu_count() or 1
    cpu_quota = read_cgroup_cpu_quota()
    if cpu_quota:
        quota, period = cpu_quota
        count = min(count, max(1, math.ceil(quota / period)))
    return count


def inference_threads() -> int:
    value = os.environ.get("EMBEDDINGS_NUM_THREADS", "").strip()
    if not value:
        return default_num_threads()
    if not value.isdecimal() or int(value) < 1:
        raise ValueError("EMBEDDINGS_NUM_THREADS must be a positive integer")
    return int(value)


session_options = ort.SessionOptions()
session_options.intra_op_num_threads = inference_threads()
model_path = os.path.join(MODEL_DIR, "model.onnx")
session = ort.InferenceSession(
    model_path, session_options, providers=["CPUExecutionProvider"]
)

# Inference already uses every thread, so parallel requests would oversubscribe.
inference_lock = threading.Lock()
# Requests wait here, not in a thread, so ones whose client left can be skipped.
request_lock = asyncio.Lock()


def mean_pooling(
    token_embeddings: np.ndarray, attention_mask: np.ndarray
) -> np.ndarray:
    input_mask_expanded = np.expand_dims(attention_mask, -1)
    input_mask_expanded = np.broadcast_to(
        input_mask_expanded, token_embeddings.shape
    ).astype(float)
    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask


def embed_batch(texts: list[str]) -> list[list[float]]:
    encodings = tokenizer.encode_batch(texts)
    ort_inputs = {
        "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
        "attention_mask": np.array(
            [e.attention_mask for e in encodings], dtype=np.int64
        ),
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
    }

    ort_outputs = session.run(None, ort_inputs)
    token_embeddings = ort_outputs[0]

    embeddings = mean_pooling(token_embeddings, ort_inputs["attention_mask"])
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings.tolist()


def compute_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings = []
    with inference_lock:
        for start in range(0, len(texts), INFERENCE_BATCH_SIZE):
            embeddings.extend(embed_batch(texts[start : start + INFERENCE_BATCH_SIZE]))
    return embeddings


def is_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode()
    except UnicodeEncodeError:
        # JSON allows lone surrogates, which the tokenizer can't encode.
        return False
    return True


async def read_body(request: Request) -> bytes | None:
    """Return the request body, or None when it's larger than MAX_BODY_BYTES."""

    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return None
    return bytes(body)


async def embed(request: Request) -> JSONResponse:
    try:
        body = await read_body(request)
        data = None if body is None else json.loads(body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if body is None:
        return JSONResponse({"error": "Request body over 1 MiB"}, status_code=413)

    if not isinstance(data, dict) or "texts" not in data:
        return JSONResponse({"error": "Missing texts field"}, status_code=400)

    texts = data["texts"]
    if isinstance(texts, str):
        texts = [texts]

    if not isinstance(texts, list) or not all(is_text(text) for text in texts):
        return JSONResponse(
            {"error": "texts must be a string or a list of strings"}, status_code=400
        )

    if not texts:
        return JSONResponse({"error": "Empty texts field"}, status_code=400)

    if len(texts) > MAX_TEXTS:
        return JSONResponse(
            {"error": f"At most {MAX_TEXTS} texts per request"}, status_code=400
        )

    async with request_lock:
        if await request.is_disconnected():
            return JSONResponse({"error": "Client disconnected"}, status_code=499)
        # Off the event loop, so health checks still answer during long requests.
        embeddings = await run_in_threadpool(compute_embeddings, texts)

    return JSONResponse({"embeddings": embeddings})


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy"})


app = Starlette(
    routes=[
        Route("/embed", embed, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ]
)
