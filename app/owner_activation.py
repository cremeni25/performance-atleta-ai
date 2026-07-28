from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/owner", tags=["owner-activation"])

OWNER_EMAIL = os.getenv("AGP_OWNER_EMAIL", "anderson@cremeni.com.br")
OWNER_AUTH_ID = os.getenv("AGP_OWNER_AUTH_ID", "14737212-032c-4b69-a6cb-a6fe80e8cf11")
ACTIVATION_CODE_SHA256 = "38b3e9a40a57eb01e6b53121ae1208d46d716b931727a314093571c06823d74d"


class OwnerActivationRequest(BaseModel):
    email: str
    activation_code: str
    new_password: str


def _validate_password(value: str) -> bool:
    return (
        len(value) >= 12
        and re.search(r"[a-z]", value) is not None
        and re.search(r"[A-Z]", value) is not None
        and re.search(r"\d", value) is not None
        and re.search(r"[^A-Za-z0-9]", value) is not None
    )


def _admin_headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Serviço de ativação indisponível")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _user_url() -> str:
    base = os.getenv("SUPABASE_URL")
    if not base:
        raise HTTPException(status_code=503, detail="Serviço de ativação indisponível")
    return f"{base.rstrip('/')}/auth/v1/admin/users/{OWNER_AUTH_ID}"


@router.post("/activate")
def activate_owner(payload: OwnerActivationRequest):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="E-mail inválido")
    if not hmac.compare_digest(email, OWNER_EMAIL.lower()):
        raise HTTPException(status_code=403, detail="Ativação não autorizada")

    supplied_hash = hashlib.sha256(payload.activation_code.strip().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(supplied_hash, ACTIVATION_CODE_SHA256):
        raise HTTPException(status_code=403, detail="Código de ativação inválido")

    if not _validate_password(payload.new_password):
        raise HTTPException(
            status_code=422,
            detail="A senha deve ter no mínimo 12 caracteres, com maiúscula, minúscula, número e símbolo",
        )

    user_response = requests.get(_user_url(), headers=_admin_headers(), timeout=15)
    if user_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível consultar o usuário proprietário")

    user = user_response.json()
    metadata = user.get("user_metadata") or {}
    if metadata.get("agp_owner_activation_completed") is True:
        raise HTTPException(status_code=409, detail="A ativação do proprietário já foi concluída")

    metadata.update(
        {
            "tipo_usuario": "master",
            "is_owner": True,
            "agp_initial_password_issued": False,
            "agp_password_changed": True,
            "agp_owner_activation_completed": True,
            "agp_owner_activation_completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    update_response = requests.put(
        _user_url(),
        headers=_admin_headers(),
        json={
            "password": payload.new_password,
            "email_confirm": True,
            "user_metadata": metadata,
        },
        timeout=15,
    )
    if update_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível concluir a ativação")

    return {"status": "activated", "message": "Acesso proprietário ativado com sucesso"}
