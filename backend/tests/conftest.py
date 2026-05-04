"""Pytest config — adds backend/ to sys.path so `import app.*` resolves
when running `pytest` from anywhere inside the project.
"""
import sys
from pathlib import Path

# backend/tests/conftest.py → backend/ is two levels up from this file's parent
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
