"""NEXUS EDGE control-plane primitives (initial in-memory pilot)."""
from .manager import EdgeManager, EdgeError, sign_message

__all__ = ["EdgeManager", "EdgeError", "sign_message"]
