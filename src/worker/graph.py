"""LangGraph StateGraph for the autonomous task worker."""

from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from src.worker.executor import executor_node
from src.worker.observer import observer_node
from src.worker.planner import planner_node
from src.worker.reporter import reporter_node
from src.worker.state import TaskWorkerState
from src.worker.tools import ToolRegistry, create_default_registry
from src.worker.verifier import verifier_node


def _route_after_planning(state: TaskWorkerState) -> Literal["executor", "reporter", "__end__"]:
    if state.status == "awaiting_user":
        return END
    if state.status == "failed":
        return "reporter"
    return "executor"


def _route_after_execution(state: TaskWorkerState) -> Literal["observer", "verifier", "reporter"]:
    if state.status == "verifying":
        return "verifier"
    if state.status == "failed":
        return "reporter"
    return "observer"


def _route_after_observation(state: TaskWorkerState) -> Literal["executor", "verifier", "reporter", "__end__"]:
    if state.status == "awaiting_user":
        return END
    if state.status == "verifying":
        return "verifier"
    if state.status == "failed":
        return "reporter"
    return "executor"


def _route_after_verification(state: TaskWorkerState) -> Literal["reporter"]:
    return "reporter"


def build_task_worker_graph(
    registry: ToolRegistry | None = None,
) -> StateGraph:
    """Build and compile the autonomous task worker state graph."""
    tools = registry or create_default_registry()

    graph = StateGraph(TaskWorkerState)

    graph.add_node("planner", planner_node)
    graph.add_node("executor", partial(executor_node, registry=tools))
    graph.add_node("observer", observer_node)
    graph.add_node("verifier", partial(verifier_node, registry=tools))
    graph.add_node("reporter", reporter_node)

    graph.set_entry_point("planner")

    graph.add_conditional_edges("planner", _route_after_planning)
    graph.add_conditional_edges("executor", _route_after_execution)
    graph.add_conditional_edges("observer", _route_after_observation)
    graph.add_conditional_edges("verifier", _route_after_verification)
    graph.add_edge("reporter", END)

    return graph.compile()


async def run_task_worker(
    task: str,
    *,
    user_input: str | None = None,
    existing_state: dict[str, Any] | None = None,
    registry: ToolRegistry | None = None,
) -> TaskWorkerState:
    """Entrypoint to execute an autonomous task.

    Handles tool lifecycle (e.g. starting/stopping browser) cleanly.
    """
    tools = registry or create_default_registry()

    browser = tools.get("browser")
    if browser and hasattr(browser, "start"):
        await browser.start()

    try:
        app = build_task_worker_graph(tools)

        if existing_state:
            initial = TaskWorkerState.model_validate(existing_state)
            if user_input:
                initial.user_input = user_input
                initial.status = "planning"
        else:
            initial = TaskWorkerState(task=task)

        result = await app.ainvoke(initial)
        return TaskWorkerState.model_validate(result)

    finally:
        if browser and hasattr(browser, "stop"):
            await browser.stop()
