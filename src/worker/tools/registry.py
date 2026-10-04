"""Tool registry for discovering and dispatching tools."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    output: str
    error: str | None = None
    screenshot: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)



class WorkerTool(Protocol):
    name: str
    description: str

    async def run(self, params: dict[str, Any]) -> ToolResult: ...


class ToolRegistry:
    """Registry managing available worker tools."""

    def __init__(self) -> None:
        self._tools: dict[str, WorkerTool] = {}

    def register(self, tool: WorkerTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> WorkerTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_descriptions(self) -> str:
        lines = []
        for name, tool in sorted(self._tools.items()):
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    async def run(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool '{tool_name}'. Available: {self.list_tools()}",
            )
        try:
            return await tool.run(params)
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' failed with {type(exc).__name__}: {exc}",
            )
