from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from aurora_serve.design_skills.service import DesignSkillService

router = APIRouter(prefix="/design-skills", tags=["design-skills"])


class DesignSkillManagementUpdate(BaseModel):
    hidden: bool | None = None
    status: str | None = None


def get_design_skill_service(request: Request) -> DesignSkillService:
    return request.app.state.design_skill_service


@router.get("")
def list_design_skills(
    include_hidden: bool = False,
    service: DesignSkillService = Depends(get_design_skill_service),
):
    skills = [
        skill.to_dict(include_body=False)
        for skill in service.list_skills(include_hidden=include_hidden)
    ]
    return {"skills": skills, "total": len(skills)}


@router.get("/adapters")
def get_design_skill_adapters(service: DesignSkillService = Depends(get_design_skill_service)):
    return service.adapter_backlog()


@router.get("/{skill_id}")
def get_design_skill(skill_id: str, service: DesignSkillService = Depends(get_design_skill_service)):
    skill = service.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Design skill not found")
    return skill.to_dict(include_body=True, files=service.list_files(skill_id))


@router.patch("/{skill_id}/management")
def update_design_skill_management(
    skill_id: str,
    update: DesignSkillManagementUpdate,
    service: DesignSkillService = Depends(get_design_skill_service),
):
    skill = service.update_management(
        skill_id,
        hidden=update.hidden,
        status=update.status,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Design skill not found")
    return skill.to_dict(include_body=False)


@router.get("/{skill_id}/files")
def list_design_skill_files(skill_id: str, service: DesignSkillService = Depends(get_design_skill_service)):
    if service.get_skill(skill_id) is None:
        raise HTTPException(status_code=404, detail="Design skill not found")
    return {"files": service.list_files(skill_id)}
