"""Authenticated profile proposal and confirmation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import User
from server.security.permissions import get_current_user
from server.services.profile_extraction import (
    ConsentRequired,
    ProfileExtractionError,
    ProfileService,
    SourceDocumentNotFound,
)


router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProposalPayload(BaseModel):
    document_ids: list[str] = Field(min_length=1)


class ConfirmProposalPayload(BaseModel):
    accepted_fields: list[str]


def get_service(request: Request, db: Session) -> ProfileService:
    return ProfileService(db, request.app.state.object_storage, request.app.state.llm_provider)


def proposal_view(proposal) -> dict:
    return {
        "id": proposal.id,
        "status": proposal.status,
        "data": proposal.proposed_data,
        "source_refs": proposal.source_refs,
        "accepted_fields": proposal.accepted_fields,
        "created_at": proposal.created_at,
        "confirmed_at": proposal.confirmed_at,
    }


def profile_view(profile) -> dict:
    return {
        "id": profile.id,
        "version": profile.version,
        "status": profile.status,
        "data": profile.data,
        "source_refs": profile.source_refs,
        "created_at": profile.created_at,
        "confirmed_at": profile.confirmed_at,
    }


@router.post("/proposals", status_code=status.HTTP_201_CREATED)
def create_proposal(
    payload: ProposalPayload,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        proposal = get_service(request, db).create_proposal(user.id, payload.document_ids)
    except ConsentRequired as exc:
        raise HTTPException(status_code=403, detail="ai consent required") from exc
    except SourceDocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return proposal_view(proposal)


@router.post("/proposals/{proposal_id}/confirm")
def confirm_proposal(
    proposal_id: str,
    payload: ConfirmProposalPayload,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        profile = get_service(request, db).confirm_proposal(
            user.id,
            proposal_id,
            payload.accepted_fields,
        )
    except ProfileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return profile_view(profile)


@router.get("")
def get_profile(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_service(request, db).get_confirmed_profile(user.id)
    return None if profile is None else profile_view(profile)
