# CPU-only image — no GPU/CUDA runtime is required (research.md §4a).
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first (better layer caching); pytorch-cpu index in
# pyproject.toml ensures the CPU-only torch wheel is pulled, not the
# CUDA-bundled default (research.md §4a).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

# Pre-download the embedding model weights at build time so the container
# has no runtime dependency on Hugging Face Hub network access
# (quickstart.md, research.md §4a). Uses the same EMBEDDING_MODEL_NAME
# default as config.py; override the build arg if that default changes.
ARG EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-small
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

# Weights are already in the image's local Hugging Face cache above — no
# runtime container start should ever reach out to huggingface.co again.
# Set only after the download step so the RUN above still has network
# access; LocalSentenceTransformerEmbeddingProvider additionally passes
# local_files_only=True to the constructor as a second, explicit guard.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 8000

# --factory: main.py deliberately has no module-level `app` (see main.py
# docstring) so importing it never has the side effect of constructing
# real providers / loading the real embedding model.
CMD ["uv", "run", "uvicorn", "albercik_chatbot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
