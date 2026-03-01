from __future__ import annotations

from openai import OpenAI

from db.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY)


def embed_task(task: str) -> list[float]:
    """Return a normalized embedding vector for a task description."""
    response = _client.embeddings.create(
        input=task,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding
