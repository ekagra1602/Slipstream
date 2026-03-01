from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

DB_NAME = "dombot"
COLLECTION_TASK_NODES = "task_nodes"
VECTOR_INDEX_NAME = "task_vector_index"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
