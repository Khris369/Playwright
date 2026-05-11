from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.editor_assistant import EditorAssistantRequest, EditorAssistantResponse
from app.services.troubleshoot_ai_service import TroubleshootAIService

router = APIRouter(prefix="/editor-assistant", tags=["editor-assistant"])


@router.post("", response_model=EditorAssistantResponse)
def ask_editor_assistant(payload: EditorAssistantRequest) -> EditorAssistantResponse:
    prompt = TroubleshootAIService.build_editor_assistant_prompt(
        question=payload.question,
        html_snippet=payload.html_snippet,
        workflow_id=payload.workflow_id,
        workflow_version_id=payload.workflow_version_id,
        current_definition_json=payload.current_definition_json,
    )
    try:
        used_model, answer = TroubleshootAIService.call_chat_model(
            prompt=prompt,
            model=payload.model,
            temperature=payload.temperature,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Editor assistant AI error: {exc}",
        ) from exc
    return EditorAssistantResponse(model=used_model, answer=answer)
