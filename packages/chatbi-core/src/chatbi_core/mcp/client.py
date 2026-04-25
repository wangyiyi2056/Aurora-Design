"""MCP Client for ChatBI - connects to MCP servers."""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncIterator

from chatbi_core.mcp.config import MCPServerConfig


@dataclass
class MCPTool:
    """A tool from an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str
    annotations: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolResult:
    """Result from MCP tool execution."""
    tool_name: str
    server_name: str
    content: Any
    is_error: bool = False
    error_message: Optional[str] = None


class MCPConnection:
    """Connection to an MCP server via JSON-RPC."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._connected: bool = False
        self._tools: List[MCPTool] = []

    async def start(self) -> bool:
        """Start the MCP server process."""
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.config.env)

            # Start process
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

            # Initialize connection
            await self._send_initialize()
            self._connected = True

            # List tools
            await self._list_tools()

            return True
        except Exception as e:
            return False

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server not started")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
            "params": params,
        }

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        # Read response
        if self.process.stdout:
            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line)

        return {"error": "No response"}

    async def _send_initialize(self) -> None:
        """Send initialize request."""
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
            },
            "clientInfo": {
                "name": "ChatBI",
                "version": "0.2.0",
            },
        })

        # Send initialized notification
        if self.process and self.process.stdin:
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            self.process.stdin.write(json.dumps(notification) + "\n")
            self.process.stdin.flush()

    async def _list_tools(self) -> None:
        """List available tools from server."""
        response = await self._send_request("tools/list", {})
        tools_data = response.get("result", {}).get("tools", [])

        self._tools = []
        for tool in tools_data:
            self._tools.append(MCPTool(
                name=tool.get("name", "unknown"),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
                server_name=self.config.name,
                annotations=tool.get("annotations", {}),
            ))

    def get_tools(self) -> List[MCPTool]:
        """Get list of tools from this server."""
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """Call a tool on this server."""
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

        result = response.get("result", {})
        content = result.get("content", [])
        is_error = result.get("isError", False)

        # Extract text content
        text_content = ""
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_content += item.get("text", "")

        return MCPToolResult(
            tool_name=name,
            server_name=self.config.name,
            content=text_content,
            is_error=is_error,
            error_message=text_content if is_error else None,
        )

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self._connected = False


class MCPClient:
    """MCP Client managing connections to multiple servers."""

    def __init__(self):
        self._connections: Dict[str, MCPConnection] = {}
        self._tools: Dict[str, MCPTool] = {}  # tool_name -> tool

    async def connect(self, config: MCPServerConfig) -> bool:
        """Connect to an MCP server."""
        if config.disabled:
            return False

        connection = MCPConnection(config)
        success = await connection.start()

        if success:
            self._connections[config.name] = connection

            # Register tools
            for tool in connection.get_tools():
                self._tools[tool.name] = tool

        return success

    async def connect_all(self, configs: Dict[str, MCPServerConfig]) -> Dict[str, bool]:
        """Connect to all configured servers."""
        results: Dict[str, bool] = {}
        for name, config in configs.items():
            results[name] = await self.connect(config)
        return results

    def disconnect(self, name: str) -> None:
        """Disconnect from a server."""
        connection = self._connections.get(name)
        if connection:
            connection.stop()
            # Remove tools from this server
            for tool_name, tool in list(self._tools.items()):
                if tool.server_name == name:
                    del self._tools[tool_name]
            del self._connections[name]

    def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for name in list(self._connections.keys()):
            self.disconnect(name)

    def get_tools(self) -> List[MCPTool]:
        """Get all tools from all servers."""
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        """Get all tool names (for tool search)."""
        return list(self._tools.keys())

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """Call a tool on the appropriate server."""
        tool = self._tools.get(name)
        if not tool:
            return MCPToolResult(
                tool_name=name,
                server_name="",
                content="",
                is_error=True,
                error_message=f"Tool '{name}' not found",
            )

        connection = self._connections.get(tool.server_name)
        if not connection:
            return MCPToolResult(
                tool_name=name,
                server_name=tool.server_name,
                content="",
                is_error=True,
                error_message=f"Server '{tool.server_name}' not connected",
            )

        return await connection.call_tool(name, arguments)

    def get_server_status(self) -> Dict[str, bool]:
        """Get connection status for all servers."""
        return {
            name: conn._connected
            for name, conn in self._connections.items()
        }

    def estimate_context_cost(self) -> int:
        """Estimate token cost for tool definitions."""
        # Each tool name ~2 tokens, full definition ~50-100 tokens
        return len(self._tools) * 2  # Name-only cost