from pydantic import BaseModel, Field


class WorkflowMemberAssignment(BaseModel):
    user_id: int = Field(ge=1)
    permissions: list[str] = Field(min_length=1, max_length=3)


class WorkflowMembersUpdate(BaseModel):
    members: list[WorkflowMemberAssignment] = Field(max_length=100)


class WorkflowMemberResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    permissions: list[str]
