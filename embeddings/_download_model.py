#!/usr/bin/env python3
"""Download and convert the embedding model to ONNX format."""

from huggingface_hub import snapshot_download
from transformers import AutoTokenizer
import os
import shutil

MODEL_ID = "optimum/all-MiniLM-L6-v2"
OUTPUT_DIR = "/model"

print(f"Downloading {MODEL_ID} from Hugging Face...")
local_dir = snapshot_download(repo_id=MODEL_ID, allow_patterns=["*.onnx", "*.json", "*.txt"])

print(f"Saving tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
os.makedirs(OUTPUT_DIR, exist_ok=True)
tokenizer.save_pretrained(OUTPUT_DIR)

print("Copying ONNX model files...")
for item in os.listdir(local_dir):
    src = os.path.join(local_dir, item)
    dst = os.path.join(OUTPUT_DIR, item)
    if os.path.isfile(src):
        shutil.copy(src, dst)

print("Done! ONNX model is ready at", OUTPUT_DIR)
