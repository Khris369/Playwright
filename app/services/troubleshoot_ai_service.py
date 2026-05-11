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
            "You are an expert Playwright automation engineer helping users build and edit workflow JSON definitions. "
            "Your goal is to provide precise, highly resilient selectors and practical step configurations. "
            "Always prioritize Playwright's best practices (e.g., role/text selectors over fragile CSS, unless IDs are explicitly unique). "
            "If an HTML snippet is provided, analyze it carefully for tricky elements like duplicate IDs, hidden inputs, or Select2 dropdowns, and recommend the exact locator strategy. "
            "When suggesting JSON snippets, ensure they are 100% syntactically valid and use the correct property names (e.g., 'selector', 'index', 'value'). "
            "Return a clear, concise response structured as follows:\n"
            "1. **Recommendation:** Direct answer to the question.\n"
            "2. **Why:** Brief technical rationale.\n"
            "3. **Example Step JSON:** A complete, copy-pasteable JSON block for the step."
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
            "You are an expert Playwright automation engineer troubleshooting a failed workflow run. "
            "Carefully analyze the provided error_summary and step logs to determine exactly why the step failed. "
            "Look out for common issues such as: strict mode violations, hidden elements (like Select2 dropdowns), timeout due to slow AJAX, or duplicate IDs. "
            "Return ONLY valid JSON with this exact shape:\n"
            "{\n"
            "  \"root_cause\": \"Detailed technical explanation of what caused the failure.\",\n"
            "  \"fixes\": [\"Actionable step 1\", \"Actionable step 2\"],\n"
            "  \"fallback_selectors\": [\"More robust CSS or role-based Playwright selector 1\", \"Selector 2\"],\n"
            "  \"corrected_steps\": [{\"type\": \"...\", \"selector\": \"...\"}],\n"
            "  \"verification_checklist\": [\"What the user should manually check in the DOM or UI\"]\n"
            "}\n"
            "Do NOT wrap the response in markdown code fences (no ```json ... ```). Return raw JSON only."
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
