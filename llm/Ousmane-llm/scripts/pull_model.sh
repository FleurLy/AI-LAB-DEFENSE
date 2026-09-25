#!/bin/sh
set -eu

MODEL="${LLM_MODEL:-qwen3.5:4b}"
echo "Pulling ${MODEL}..."
ollama pull "${MODEL}"

