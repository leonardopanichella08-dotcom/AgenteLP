"""Vercel serverless entry point. Vercel expects `api/index.py` exposing `app`."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: E402,F401
