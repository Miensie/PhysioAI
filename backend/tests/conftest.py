"""
conftest.py — Chargé automatiquement par pytest avant tous les tests.
Configure sys.path pour que `from main import app` fonctionne
peu importe depuis quel répertoire pytest est lancé.
"""
import sys
import os

# backend/tests/conftest.py → remonter à backend/
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
