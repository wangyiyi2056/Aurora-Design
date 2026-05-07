"""Application status and usage tracking system.

Provides:
- StatusData: complete app status snapshot (model, cost, context, tools, git, memory)
- CostTracker: session token usage, cost, and performance tracking
- Model pricing tiers for major LLM providers
"""

from aurora_core.status.models import (
    StatusData,
    ModelInfo,
    ContextWindow,
    CurrentUsage,
    CostStats,
    WorkspaceInfo,
    ToolStats,
    GitInfo,
    MemoryStats,
    PermissionMode,
)
from aurora_core.status.tracker import (
    CostTracker,
    ModelUsage,
    MODEL_PRICING,
    DEFAULT_PRICING,
)

__all__ = [
    "StatusData",
    "ModelInfo",
    "ContextWindow",
    "CurrentUsage",
    "CostStats",
    "WorkspaceInfo",
    "ToolStats",
    "GitInfo",
    "MemoryStats",
    "PermissionMode",
    "CostTracker",
    "ModelUsage",
    "MODEL_PRICING",
    "DEFAULT_PRICING",
]
