from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from config import env


class TroubleshootAIService:
    @staticmethod
    def build_editor_assistant_prompt(
        question: str,
        html_snippet: str | None = None,
        workflow_id: int | None = None,
        workflow_version_id: int | None = None,
        current_definition_json: dict[str, Any] | None = None,
    ) -> str:
        context = {
            "workflow_id": workflow_id,
            "workflow_version_id": workflow_version_id,
            "current_definition_json": current_definition_json or {},
            "html_snippet": html_snippet or "",
        }
        instructions = (
            "You are an assistant helping users edit browser automation workflows. "
            "Give practical, concise guidance for step configuration and selectors. "
            "When relevant, suggest exact JSON snippets for steps. "
            "If asked about click_by_role, provide recommended role/name/scope_selector/exact/nth values. "
            "If HTML snippet is provided, derive selectors/role-targeting from it. "
            "Return plain text with short sections: Recommendation, Why, Example Step JSON."
        )
        return (
            f"{instructions}\n\n"
            f"User question:\n{question}\n\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}"
        )

    @staticmethod
    def build_prompt(
        run: dict[str, Any], step_runs: list[dict[str, Any]], extra_prompt: str | None = None
    ) -> str:
        failed_steps = [
            {
                "step_index": row.get("step_index"),
                "step_type": row.get("step_type"),
                "args_json": row.get("args_json"),
                "error_text": row.get("error_text"),
                "log_text": row.get("log_text"),
            }
            for row in step_runs
            if str(row.get("status", "")).lower() == "failed"
        ]

        payload = {
            "run_id": run.get("id"),
            "workflow_version_id": run.get("workflow_version_id"),
            "status": run.get("status"),
            "error_summary": run.get("error_summary"),
            "inputs_json": run.get("inputs_json"),
            "failed_steps": failed_steps,
        }

        instructions = (
            "You are troubleshooting a Playwright workflow run. "
            "Analyze the failure and return ONLY valid JSON with this exact shape: "
            "{"
            "\"root_cause\": string, "
            "\"fixes\": [string], "
            "\"fallback_selectors\": [string], "
            "\"corrected_steps\": [object], "
            "\"verification_checklist\": [string]"
            "}. "
            "Do not include markdown code fences."
        )

        if extra_prompt:
            instructions += f"\nAdditional context from user: {extra_prompt.strip()}"

        return f"{instructions}\n\nRun data:\n{json.dumps(payload, indent=2, default=str)}"

    @staticmethod
    def call_chat_model(
        prompt: str, model: str | None = None, temperature: float = 0.2
    ) -> tuple[str, str]:
        api_key = env("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        endpoint = env("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
        chosen_model = model or env("OPENAI_CHAT_MODEL", "gpt-4o-mini")

        body = {
            "model": chosen_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI HTTP error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI connection error: {exc}") from exc

        parsed = json.loads(raw)
        content = (
            parsed.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not content:
            raise RuntimeError("OpenAI response missing choices[0].message.content")
        return chosen_model, str(content)

    @staticmethod
    def parse_structured_analysis(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise RuntimeError("Structured analysis is not a JSON object")
        return {
            "root_cause": parsed.get("root_cause", ""),
            "fixes": parsed.get("fixes", []),
            "fallback_selectors": parsed.get("fallback_selectors", []),
            "corrected_steps": parsed.get("corrected_steps", []),
            "verification_checklist": parsed.get("verification_checklist", []),
        }
