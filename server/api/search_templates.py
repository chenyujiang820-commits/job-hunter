"""Search template endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import SearchTemplate, User
from server.security.permissions import get_current_user
from server.services.evaluation import SearchTemplateInput, SearchTemplateService


router = APIRouter(prefix="/api/search-templates", tags=["search-templates"])


class SearchTemplatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    keywords: list[str] = []
    cities: list[str] = []
    industries: list[str] = []
    experience: str = ""
    education: str = ""
    salary_reference: int | None = None
    work_modes: list[str] = []
    hard_exclusions: list[str] = []
    weights: dict[str, int] = {}


def template_view(template: SearchTemplate) -> dict:
    return {"id": template.id, "name": template.name, "data": template.data, "is_default": template.is_default}


@router.post("", status_code=201)
def create_template(
    payload: SearchTemplatePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = SearchTemplateService(db).create(user.id, SearchTemplateInput(**payload.model_dump()))
    return template_view(template)


@router.get("")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [template_view(template) for template in SearchTemplateService(db).list_for_user(user.id)]
