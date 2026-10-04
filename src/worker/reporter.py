"""Reporter node: produces the final execution summary with evidence."""

from typing import Any

from src.worker.state import TaskWorkerState


def _build_markdown_report(state: TaskWorkerState) -> str:
    sections = []

    status_icon = "PASS" if state.status == "completed" else "FAIL"
    sections.append(f"# Task Execution Report [{status_icon}]\n")
    sections.append(f"**Task:** {state.task}")
    sections.append(f"**Goal:** {state.goal}\n")

    # Plan & Execution Summary
    total_steps = len(state.plan)
    completed_steps = sum(1 for s in state.plan if s.status == "done")
    retried_steps = sum(s.retries for s in state.plan)
    sections.append("## Execution Summary")
    sections.append(f"- **Steps Completed:** {completed_steps}/{total_steps}")
    sections.append(f"- **Total Actions:** {len(state.actions)}")
    sections.append(f"- **Retries:** {retried_steps}")
    sections.append(f"- **Verification:** {'PASSED' if state.verified else 'FAILED'}")
    if state.verification_details:
        sections.append(f"- **Verification Details:** {state.verification_details}")
    sections.append("")

    # Action Log
    if state.actions:
        sections.append("## Action Log")
        for a in state.actions:
            status = "OK" if a.success else f"ERROR: {a.error}"
            sections.append(f"- **Step {a.step_index}** `[{a.tool}]`: {status}")
            if a.output:
                truncated = a.output[:150].replace("\n", " ")
                sections.append(f"  - *Output:* {truncated}")
        sections.append("")

    # Evidence
    if state.evidence:
        sections.append("## Visual Evidence")
        for path in state.evidence:
            sections.append(f"- Screenshot: `{path}`")
        sections.append("")

    # Working Memory
    if state.memory:
        sections.append("## Extracted Data")
        for k, v in state.memory.items():
            sections.append(f"- **{k}:** {v}")
        sections.append("")

    return "\n".join(sections)


async def reporter_node(state: TaskWorkerState) -> dict[str, Any]:
    """Generate markdown summary report."""
    summary = _build_markdown_report(state)
    return {"summary": summary}
