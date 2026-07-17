from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.schemas.editor_assistant import EditorAssistantRequest, EditorAssistantResponse
from app.services.troubleshoot_ai_service import TroubleshootAIService
from app.engine.registry import STEP_REGISTRY
from app.core.auth import require_permission

router = APIRouter(prefix="/editor-assistant", tags=["editor-assistant"])
logger = logging.getLogger(__name__)


@router.post("", response_model=EditorAssistantResponse)
def ask_editor_assistant(payload: EditorAssistantRequest, user: dict = Depends(require_permission("workflow.edit"))) -> EditorAssistantResponse:
    if payload.current_definition_json is not None and len(json.dumps(payload.current_definition_json, separators=(",", ":")).encode("utf-8")) > 512 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Workflow context is too large")
    prompt = TroubleshootAIService.build_editor_assistant_prompt(
        question=payload.question,
        html_snippet=payload.html_snippet,
        workflow_id=payload.workflow_id,
        workflow_version_id=payload.workflow_version_id,
        current_definition_json=payload.current_definition_json,
        available_step_types=sorted(STEP_REGISTRY),
    )
    try:
        used_model, raw_answer = TroubleshootAIService.call_chat_model(
            prompt=prompt,
            model=payload.model,
            temperature=payload.temperature,
        )
        answer, proposed_actions = TroubleshootAIService.parse_editor_assistant_response(raw_answer)
        actions = []
        for action in proposed_actions:
            step = STEP_REGISTRY.get(action["step_type"])
            if step is None:
                continue
            try:
                validated = step.args_model.model_validate(action["args"])
            except ValidationError:
                continue
            actions.append({"action": "add_step", "step_type": action["step_type"], "args": validated.model_dump(mode="json")})
    except RuntimeError as exc:
        logger.exception("Editor assistant provider or validation failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Editor assistant could not produce a safe response",
        ) from exc
    return EditorAssistantResponse(model=used_model, answer=answer, actions=actions)
