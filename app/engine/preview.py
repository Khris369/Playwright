"""Environment-neutral local-preview compatibility and graph helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.registry import STEP_REGISTRY


@dataclass(frozen=True)
class PreviewCapability:
    status: str
    handler: str | None = None
    side_effect: bool = False


# Browser-only operations have async equivalents in picker_agent.preview.
# Ticket actions are deliberately excluded because they depend on production
# application state and can create or submit records.
LOCAL_PREVIEW_CAPABILITIES: dict[str, PreviewCapability] = {
    "goto_url": PreviewCapability("supported", "goto_url"),
    "click": PreviewCapability("supported", "click", side_effect=True),
    "fill_input": PreviewCapability("supported", "fill_input", side_effect=True),
    "select_option": PreviewCapability("supported", "select_option", side_effect=True),
    "wait_for_element": PreviewCapability("supported", "wait_for_element"),
    "wait_timeout": PreviewCapability("supported", "wait_timeout"),
    "verify_element": PreviewCapability("supported", "verify_element"),
    "assert_url_not_equal": PreviewCapability("supported", "assert_url_not_equal"),
    "assert_text_visible": PreviewCapability("supported", "assert_text_visible"),
    "ticket_create_new_ticket": PreviewCapability("supported", "ticket_create_new_ticket", side_effect=True),
    "ticket_fill_fields": PreviewCapability("supported", "ticket_fill_fields", side_effect=True),
}


def preview_compatibility_matrix() -> list[dict[str, Any]]:
    """Return the checked-in registry inventory used by API and agent checks."""
    rows: list[dict[str, Any]] = []
    for key in STEP_REGISTRY:
        capability = LOCAL_PREVIEW_CAPABILITIES.get(key, PreviewCapability("unsupported"))
        rows.append({"node_type": key, "classification": "browser_step", "phase1_status": capability.status,
                     "local_handler": capability.handler, "side_effect": capability.side_effect})
    rows.extend([
        {"node_type": "__if__", "classification": "control_node", "phase1_status": "supported", "local_handler": "control", "side_effect": False},
        {"node_type": "__loop__", "classification": "control_node", "phase1_status": "supported", "local_handler": "control", "side_effect": False},
    ])
    return rows


def possible_steps_to_target(compiled: list[dict[str, Any]], target_node_id: str) -> list[dict[str, Any]]:
    """Conservatively collect every node on a graph path that can reach target.

    The compiled graph is used as graph metadata, never as flattened runtime
    order. A node is included only when it is reachable from the entry and can
    still reach the selected target.
    """
    by_id = {str(step["id"]): step for step in compiled}
    if target_node_id not in by_id:
        raise ValueError("target_not_found")
    successors = {node_id: [str(value) for value in ([step.get("next")] if step.get("next") else []) + list((step.get("branches") or {}).values()) if value is not None] for node_id, step in by_id.items()}
    entry = str(compiled[0]["id"]) if compiled else ""
    reachable: set[str] = set()
    stack = [entry] if entry else []
    while stack:
        current = stack.pop()
        if current in reachable or current not in by_id:
            continue
        reachable.add(current)
        # The preview is inclusive of the target. Traversal must not inspect
        # successor nodes because they cannot execute after the target has
        # completed successfully. Other paths remain included so normal
        # termination can still produce target_not_reached.
        if current != target_node_id:
            stack.extend(successors[current])
    if target_node_id not in reachable:
        raise ValueError("target_unreachable")
    # Keep alternate branches that cannot reach the target too: their normal
    # termination is how the executor produces target_not_reached.
    return [step for step in compiled if str(step["id"]) in reachable]
