from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from chatbi_core.agent.skill.base import SkillRegistry

router = APIRouter(prefix="/agent", tags=["agent"])


def get_skill_registry(request: Request) -> SkillRegistry:
    registry = getattr(request.app.state, "skill_registry", None)
    if registry is None:
        registry = SkillRegistry()
        request.app.state.skill_registry = registry
    return registry


@router.get("/skills")
async def list_skills(
    registry: SkillRegistry = Depends(get_skill_registry),
) -> Dict[str, str]:
    return registry.list_skills()
