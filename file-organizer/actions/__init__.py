"""Action implementations.

Currently only the `move` action is provided. Production delivery adds
compress, rename, delete, archive, trash, and custom shell hooks.
"""
from .move import move

__all__ = ["move"]
