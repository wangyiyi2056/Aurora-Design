"""Skills API endpoint."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillInfo(BaseModel):
    name: str
    description: str
    description_cn: str
    parameters: dict
    is_builtin: bool


class SkillsListResponse(BaseModel):
    skills: list[SkillInfo]
    total: int


@router.get("", response_model=SkillsListResponse)
async def list_skills(request: Request):
    """List all registered skills with metadata."""
    skill_registry = request.app.state.skill_registry
    if not skill_registry:
        return SkillsListResponse(skills=[], total=0)

    skills_data = skill_registry.list_skills_detail()
    return SkillsListResponse(
        skills=[SkillInfo(**s) for s in skills_data],
        total=len(skills_data),
    )