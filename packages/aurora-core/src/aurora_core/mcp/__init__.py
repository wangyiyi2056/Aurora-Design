"""MCP (Model Context Protocol) integration for Aurora."""

from aurora_core.mcp.client import MCPClient
from aurora_core.mcp.config import MCPConfig, MCPServerConfig

__all__ = ["MCPClient", "MCPConfig", "MCPServerConfig"]