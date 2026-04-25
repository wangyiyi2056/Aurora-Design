"""ChatBI core framework - Claude Code architecture upgrade."""

__version__ = "0.2.0"

# Session Management
from chatbi_core.session import SessionManager, Session, SessionMessage

# Memory Management
from chatbi_core.memory import MemoryManager, MemoryEntry, MemoryType

# Hooks System
from chatbi_core.hooks import HookManager, Hook, HookType, HookMatcher

# Context Management
from chatbi_core.context import ContextCompactor, ToolSearchManager

# Subagents System
from chatbi_core.subagents import SubagentManager, SubagentDefinition

# MCP Integration
from chatbi_core.mcp import MCPClient, MCPConfig, MCPServerConfig

# Skills System
from chatbi_core.skills import SkillsLoader, SkillFile

# Permissions System
from chatbi_core.permissions import PermissionManager, PermissionMode, PermissionConfig

# Agent Skill Base (existing)
from chatbi_core.agent.skill.base import BaseSkill, SkillRegistry

__all__ = [
    # Session
    "SessionManager",
    "Session",
    "SessionMessage",
    # Memory
    "MemoryManager",
    "MemoryEntry",
    "MemoryType",
    # Hooks
    "HookManager",
    "Hook",
    "HookType",
    "HookMatcher",
    # Context
    "ContextCompactor",
    "ToolSearchManager",
    # Subagents
    "SubagentManager",
    "SubagentDefinition",
    # MCP
    "MCPClient",
    "MCPConfig",
    "MCPServerConfig",
    # Skills
    "SkillsLoader",
    "SkillFile",
    # Permissions
    "PermissionManager",
    "PermissionMode",
    "PermissionConfig",
    # Agent
    "BaseSkill",
    "SkillRegistry",
]