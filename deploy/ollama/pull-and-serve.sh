#!/bin/sh
# AI4: the local model service. Starts Ollama, downloads the open-weight model on the first run
# (it stays in the ollama-data volume) and keeps serving. The OpenAI-compatible API is
# http://llm:11434/v1 inside the compose network.
set -e
ollama serve &
server=$!
until ollama list >/dev/null 2>&1; do sleep 1; done
echo "pulling ${OLLAMA_MODEL} (first run only, a few GB)…"
ollama pull "${OLLAMA_MODEL}"
echo "model ${OLLAMA_MODEL} is ready"
wait "$server"
