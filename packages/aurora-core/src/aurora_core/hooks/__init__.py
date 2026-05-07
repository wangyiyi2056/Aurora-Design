"""Hooks system for Aurora."""

from aurora_core.hooks.schema import Hook, HookType, HookMatcher, HookResult
from aurora_core.hooks.manager import HookManager

__all__ = ["Hook", "HookType", "HookMatcher", "HookManager", "HookResult"]