"""User settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import ModelCredential, User
from server.security.permissions import get_current_user
from server.services.profile_extraction import ProfileExtractionError, ProfileService


router = APIRouter(prefix="/api/settings", tags=["settings"])


class AiConsentPayload(BaseModel):
    enabled: bool


class ModelKeyPayload(BaseModel):
    provider: str = "openai-compatible"
    api_key: str


def consent_view(user: User) -> dict:
    return {
        "enabled": bool(user.ai_processing_enabled),
        "consented_at": user.ai_consent_at,
    }


@router.get("/ai-consent")
def get_ai_consent(user: User = Depends(get_current_user)):
    return consent_view(user)


@router.api_route("/ai-consent", methods=["POST", "PATCH"])
def set_ai_consent(
    payload: AiConsentPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        updated = ProfileService(db, None, None).set_ai_consent(user.id, payload.enabled)
    except ProfileExtractionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return consent_view(updated)


@router.get("/model-key")
def get_model_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = db.scalar(
        select(ModelCredential).where(
            ModelCredential.user_id == user.id,
            ModelCredential.provider == "openai-compatible",
        )
    )
    return {"provider": "openai-compatible", "configured": credential is not None and credential.enabled}


@router.put("/model-key")
def set_model_key(
    payload: ModelKeyPayload,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.provider != "openai-compatible":
        raise HTTPException(status_code=422, detail="unsupported model provider")
    cipher = request.app.state.credential_cipher
    if cipher is None:
        raise HTTPException(status_code=503, detail="model credential encryption is not configured")
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="api key is required")
    credential = db.scalar(
        select(ModelCredential).where(
            ModelCredential.user_id == user.id,
            ModelCredential.provider == payload.provider,
        )
    )
    if credential is None:
        credential = ModelCredential(user_id=user.id, provider=payload.provider)
        db.add(credential)
    credential.encrypted_key = cipher.encrypt(api_key)
    credential.enabled = True
    db.commit()
    return {"provider": payload.provider, "configured": True}


@router.delete("/model-key", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = db.scalar(
        select(ModelCredential).where(
            ModelCredential.user_id == user.id,
            ModelCredential.provider == "openai-compatible",
        )
    )
    if credential is not None:
        credential.enabled = False
        credential.encrypted_key = ""
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
