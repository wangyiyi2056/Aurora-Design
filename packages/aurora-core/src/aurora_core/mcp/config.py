"""MCP Configuration for Aurora."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str  # Command to start the server
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    auto_approve: List[str] = field(default_factory=list)  # Tools to auto-approve

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "disabled": self.disabled,
            "auto_approve": self.auto_approve,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create from dictionary."""
        return cls(
            name=data.get("name", "unknown"),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            disabled=data.get("disabled", False),
            auto_approve=data.get("auto_approve", []),
        )


@dataclass
class MCPConfig:
    """Configuration for MCP integration."""
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)

    def add_server(self, config: MCPServerConfig) -> None:
        """Add a server configuration."""
        self.servers[config.name] = config

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration."""
        return self.servers.get(name)

    def list_servers(self) -> List[str]:
        """List all server names."""
        return list(self.servers.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "servers": {name: cfg.to_dict() for name, cfg in self.servers.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """Create from dictionary."""
        config = cls()
        for name, server_data in data.get("servers", {}).items():
            server = MCPServerConfig.from_dict(server_data)
            config.servers[name] = server
        return config

    @classmethod
    def load(cls, path: Optional[str] = None) -> "MCPConfig":
        """Load configuration from file."""
        config_path = Path(path or os.path.expanduser("~/.aurora/mcp.json"))

        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return cls.from_dict(data)
            except json.JSONDecodeError:
                pass

        return cls()

    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to file."""
        config_path = Path(path or os.path.expanduser("~/.aurora/mcp.json"))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(self.to_dict()))