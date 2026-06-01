"""Content and argument hashing — migrated from LightRAG ``utils.py``."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_mdhash_id(content: str, prefix: str = "") -> str:
    """Compute an MD5-based document ID from *content*.

    Parameters
    ----------
    content:
        The raw text content to hash.
    prefix:
        Optional prefix prepended to the hex digest (e.g. ``"doc-"``).

    Returns
    -------
    str
        ``prefix + md5_hex_digest``
    """
    return prefix + hashlib.md5(content.encode("utf-8")).hexdigest()


def compute_args_hash(*args: Any, **kwargs: Any) -> str:
    """Compute a stable hash from arbitrary arguments.

    Used primarily as a cache key for LLM response caching.

    The function serialises *args* and *kwargs* to a deterministic JSON
    string (sorted keys, ``ensure_ascii=False``) before hashing.
    """
    payload = json.dumps(
        {"args": args, "kwargs": kwargs},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def generate_cache_key(namespace: str, *args: Any, **kwargs: Any) -> str:
    """Generate a cache key scoped to *namespace*.

    Convenience wrapper around :func:`compute_args_hash`.
    """
    return compute_args_hash(namespace, *args, **kwargs)
