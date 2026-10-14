"""Proxy package forwarding to backend/app."""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

_backend_app = _backend / "app"
__path__ = [str(_backend_app)]
