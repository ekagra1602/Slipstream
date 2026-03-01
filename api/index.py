"""Vercel serverless entrypoint — re-exports the FastAPI app from frontend/server.py."""
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend.server import app  # noqa: F401, E402
