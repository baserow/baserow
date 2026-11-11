#!/usr/bin/env python3
"""Download the ONNX embedding model and configure its tokenizer."""

import json
import os
import shutil

from huggingface_hub import snapshot_download
from tokenizers import Tokenizer

MODEL_ID = "optimum/all-MiniLM-L6-v2"
# Pinned so rebuilding the image can never change the stored vectors.
MODEL_REVISION = "10244843eba3d9e479b27a4b81c94b56d8e9f4f2"
OUTPUT_DIR = os.environ.get("EMBEDDINGS_MODEL_DIR", "/model")

print(f"Downloading {MODEL_ID} from Hugging Face...")
local_dir = snapshot_download(
    repo_id=MODEL_ID,
    revision=MODEL_REVISION,
    allow_patterns=["*.onnx", "*.json", "*.txt"],
)

print("Copying ONNX model files...")
os.makedirs(OUTPUT_DIR, exist_ok=True)
for item in os.listdir(local_dir):
    src = os.path.join(local_dir, item)
    dst = os.path.join(OUTPUT_DIR, item)
    if os.path.isfile(src):
        # The cache's files are read-only, and copying that mode breaks re-runs.
        shutil.copyfile(src, dst)

print("Configuring the tokenizer...")
with open(os.path.join(local_dir, "tokenizer_config.json")) as f:
    tokenizer_config = json.load(f)
tokenizer = Tokenizer.from_file(os.path.join(local_dir, "tokenizer.json"))
# Override the file's 128-token settings to match how stored vectors were made.
tokenizer.enable_truncation(max_length=tokenizer_config["model_max_length"])
tokenizer.enable_padding(
    pad_id=tokenizer.token_to_id(tokenizer_config["pad_token"]),
    pad_token=tokenizer_config["pad_token"],
)
tokenizer.save(os.path.join(OUTPUT_DIR, "tokenizer.json"))

print("Done! ONNX model is ready at", OUTPUT_DIR)
