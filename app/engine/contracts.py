from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LocatorTarget(StrictModel):
    strategy: Literal["role", "label", "css", "text"]
    role: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=500)
    label: str | None = Field(default=None, min_length=1, max_length=500)
    selector: str | None = Field(default=None, min_length=1, max_length=1000)
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    exact: StrictBool = True

    @model_validator(mode="after")
    def validate_strategy_fields(self) -> "LocatorTarget":
        required = {
            "role": ("role", "name"),
            "label": ("label",),
            "css": ("selector",),
            "text": ("text",),
        }[self.strategy]
        allowed = set(required) | {"strategy", "exact", "scope", "match", "nth"}
        values = self.model_dump()
        missing = [field for field in required if not values.get(field)]
        if missing:
            raise ValueError(f"{self.strategy} locator requires {', '.join(missing)}")
        populated = {key for key, value in values.items() if value is not None}
        unexpected = populated - allowed
        if unexpected:
            raise ValueError(f"fields not valid for {self.strategy}: {', '.join(sorted(unexpected))}")
        if self.strategy == "css":
            selector = self.selector or ""
            lowered = selector.lower().strip()
            if lowered.startswith(("xpath=", "text=", "javascript:")) or "\x00" in selector:
                raise ValueError("selector must be CSS only")
        return self


class Locator(LocatorTarget):
    scope: LocatorTarget | None = None
    match: Literal["strict", "first", "last", "nth"] = "strict"
    nth: int | None = Field(default=None, ge=0, le=99)

    @model_validator(mode="after")
    def validate_match(self) -> "Locator":
        if self.match == "nth" and self.nth is None:
            raise ValueError("nth match requires nth")
        if self.match != "nth" and self.nth is not None:
            raise ValueError("nth is only valid with nth match")
        return self


class EmptyArgs(StrictModel):
    pass


class GotoUrlArgs(StrictModel):
    url: str = Field(min_length=1, max_length=4096)


class TargetValueArgs(StrictModel):
    target: Locator
    value: str = Field(max_length=100_000)


class ClickArgs(StrictModel):
    target: Locator


class SelectOption(StrictModel):
    by: Literal["label", "value", "index"]
    value: str | int

    @model_validator(mode="after")
    def validate_value(self) -> "SelectOption":
        if self.by == "index":
            if not isinstance(self.value, int) or isinstance(self.value, bool) or not 0 <= self.value <= 999:
                raise ValueError("index option requires an integer from 0 to 999")
        elif not isinstance(self.value, str) or not self.value or len(self.value) > 2000:
            raise ValueError(f"{self.by} option requires a non-empty string")
        return self


class SelectOptionArgs(StrictModel):
    target: Locator
    option: SelectOption


class WaitForElementArgs(StrictModel):
    target: Locator
    state: Literal["attached", "detached", "visible", "hidden"] = "visible"
    timeout_ms: int = Field(default=30_000, ge=1, le=120_000)


class WaitTimeoutArgs(StrictModel):
    timeout_ms: int = Field(default=1000, ge=0, le=120_000)


class AssertUrlNotEqualArgs(StrictModel):
    url: str = Field(min_length=1, max_length=4096)


class AssertTextVisibleArgs(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    exact: StrictBool = True


class TicketScenarioArgs(StrictModel):
    scenario_name: str = Field(min_length=1, max_length=200)


class TicketCreateArgs(StrictModel):
    target: Locator = Field(default_factory=lambda: Locator(
        strategy="role", role="button", name="Create New Ticket", exact=True
    ))
    timeout_ms: int = Field(default=30_000, ge=1, le=120_000)


class TicketField(StrictModel):
    target: Locator
    control_type: Literal["text", "textarea", "select"]
    value: str = Field(default="", max_length=100_000)
    option: SelectOption | None = None

    @model_validator(mode="after")
    def validate_control(self) -> "TicketField":
        if self.control_type == "select" and self.option is None:
            raise ValueError("select field requires option")
        if self.control_type != "select" and self.option is not None:
            raise ValueError("option is only valid for select fields")
        return self


class TicketFillFieldsArgs(StrictModel):
    fields: Annotated[list[TicketField], Field(min_length=1, max_length=100)]


class TicketSubmitArgs(StrictModel):
    submit_target: Locator = Field(default_factory=lambda: Locator(
        strategy="role", role="button", name="Submit", exact=True
    ))
    confirm_target: Locator = Field(default_factory=lambda: Locator(
        strategy="role", role="button", name="Yes", exact=True
    ))
