from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SENSITIVE_ATTRIBUTE = re.compile(r"pass|token|secret|cookie|auth|value", re.I)
VOLATILE = re.compile(r"^(css-|ng-|react|vue|ember|data-react|data-v-|_[a-z0-9]{6,})", re.I)
SAFE_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class Candidate:
    locator: dict[str, Any]
    score: int
    source: str


def redact_text(value: str | None, limit: int = 160) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())[:limit]
    return cleaned or None


def safe_attributes(attributes: dict[str, str]) -> dict[str, str]:
    return {key: value[:160] for key, value in attributes.items() if not SENSITIVE_ATTRIBUTE.search(key) and len(value) <= 160}


def _css_attr(name: str, value: str) -> str:
    return f'[{name}="{value.replace("\\", "\\\\").replace(chr(34), "\\\"")}"]'


def generate_candidates(metadata: dict[str, Any]) -> list[Candidate]:
    """Return only locators executable by the repository's existing contract."""
    attrs = safe_attributes(dict(metadata.get("attributes") or {}))
    tag = str(metadata.get("tag_name") or "*").lower()
    role = redact_text(metadata.get("role"), 50)
    name = redact_text(metadata.get("name"))
    label = redact_text(metadata.get("label"))
    text = redact_text(metadata.get("text"))
    candidates: list[Candidate] = []
    if role and name:
        candidates.append(Candidate({"strategy": "role", "role": role, "name": name, "exact": True, "match": "strict"}, 100, "accessible role"))
    if label:
        candidates.append(Candidate({"strategy": "label", "label": label, "exact": True, "match": "strict"}, 96, "label"))
    for key in ("data-testid", "data-test", "data-qa"):
        if attrs.get(key):
            candidates.append(Candidate({"strategy": "css", "selector": f"{tag}{_css_attr(key, attrs[key])}", "exact": True, "match": "strict"}, 92, "test id"))
            break
    if attrs.get("placeholder"):
        candidates.append(Candidate({"strategy": "css", "selector": f"{tag}{_css_attr('placeholder', attrs['placeholder'])}", "exact": True, "match": "strict"}, 88, "placeholder"))
    stable_id = attrs.get("id")
    if stable_id and not VOLATILE.search(stable_id):
        candidates.append(Candidate({"strategy": "css", "selector": f"#{stable_id}", "exact": True, "match": "strict"}, 86, "stable id"))
    classes = [token for token in str(attrs.get("class", "")).split() if SAFE_CLASS.fullmatch(token) and not VOLATILE.search(token)]
    if classes:
        candidates.append(Candidate({"strategy": "css", "selector": tag + "".join(f".{token}" for token in classes), "exact": True, "match": "strict"}, 78, "class"))
    for key in ("name", "aria-label", "title"):
        if attrs.get(key) and not VOLATILE.search(attrs[key]):
            candidates.append(Candidate({"strategy": "css", "selector": f"{tag}{_css_attr(key, attrs[key])}", "exact": True, "match": "strict"}, 82, key))
            break
    if text and len(text) <= 160:
        candidates.append(Candidate({"strategy": "text", "text": text, "exact": True, "match": "strict"}, 70, "visible text"))
    css = metadata.get("css")
    if isinstance(css, str) and css and len(css) <= 1000:
        candidates.append(Candidate({"strategy": "css", "selector": css, "exact": True, "match": "strict"}, 50, "css"))
    return candidates
