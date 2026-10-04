"""Tool definitions and default registry factory for the autonomous worker."""

from src.worker.tools.browser import BrowserTool
from src.worker.tools.http import HTTPTool
from src.worker.tools.registry import ToolRegistry, ToolResult, WorkerTool
from src.worker.tools.support_agent import SupportAgentTool


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry populated with all standard worker tools."""
    registry = ToolRegistry()
    registry.register(BrowserTool())
    registry.register(HTTPTool())
    registry.register(SupportAgentTool())
    return registry


def get_tool_descriptions() -> str:
    """Return human-readable tool descriptions for LLM prompts."""
    temp_reg = create_default_registry()
    return temp_reg.get_descriptions()


__all__ = [
    "BrowserTool",
    "HTTPTool",
    "SupportAgentTool",
    "ToolRegistry",
    "ToolResult",
    "WorkerTool",
    "create_default_registry",
    "get_tool_descriptions",
]
