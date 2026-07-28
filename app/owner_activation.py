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
ACTIVATION_CODE_SHA256 = "172ad9c770615e23fbf7cf8ac64b72ed3b2d2d35311fab0c7a4d69c90f7fe023"


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


def _supabase_url() -> str:
    base = os.getenv("SUPABASE_URL")
    if not base:
        raise HTTPException(status_code=503, detail="Serviço de ativação indisponível")
    return base.rstrip("/")


def _admin_headers(prefer_representation: bool = False) -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Serviço de ativação indisponível")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer_representation:
        headers["Prefer"] = "return=representation"
    return headers


def _find_user_by_email(email: str) -> dict:
    base = _supabase_url()
    headers = _admin_headers()

    for page in range(1, 101):
        response = requests.get(
            f"{base}/auth/v1/admin/users",
            headers=headers,
            params={"page": page, "per_page": 1000},
            timeout=20,
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Não foi possível consultar os usuários do AGP")

        payload = response.json()
        users = payload.get("users", []) if isinstance(payload, dict) else []

        for user in users:
            if str(user.get("email", "")).strip().lower() == email:
                return user

        if len(users) < 1000:
            break

    raise HTTPException(status_code=404, detail="Usuário proprietário não localizado no AGP")


def _user_url(user_id: str) -> str:
    return f"{_supabase_url()}/auth/v1/admin/users/{user_id}"


def ensure_owner_profile() -> dict:
    """Garante vínculo idempotente entre Auth e perfil Master."""
    email = OWNER_EMAIL.strip().lower()
    user = _find_user_by_email(email)
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=502, detail="Cadastro proprietário inconsistente")

    base = _supabase_url()
    headers = _admin_headers(prefer_representation=True)
    select_url = f"{base}/rest/v1/perfis_atletas"

    response = requests.get(
        select_url,
        headers=headers,
        params={"or": f"(auth_id.eq.{user_id},email.eq.{email})", "select": "*"},
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível consultar o perfil proprietário")

    rows = response.json() if isinstance(response.json(), list) else []
    payload_variants = [
        {"auth_id": user_id, "email": email, "nome": "Anderson Navarro", "tipo_usuario": "master", "funcao": "master"},
        {"auth_id": user_id, "email": email, "nome": "Anderson Navarro", "tipo_usuario": "master"},
        {"auth_id": user_id, "email": email, "nome": "Anderson Navarro", "funcao": "master"},
    ]

    if rows:
        row_id = rows[0].get("id")
        filters = {"id": f"eq.{row_id}"} if row_id else {"email": f"eq.{email}"}
        for profile_payload in payload_variants:
            patch = requests.patch(
                select_url,
                headers=headers,
                params=filters,
                json=profile_payload,
                timeout=20,
            )
            if patch.status_code < 400:
                return {"status": "updated", "auth_id": user_id}
    else:
        for profile_payload in payload_variants:
            insert = requests.post(
                select_url,
                headers=headers,
                json=profile_payload,
                timeout=20,
            )
            if insert.status_code < 400:
                return {"status": "created", "auth_id": user_id}

    raise HTTPException(status_code=502, detail="Não foi possível vincular o perfil Master")


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

    user = _find_user_by_email(email)
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=502, detail="Cadastro proprietário inconsistente")

    metadata = user.get("user_metadata") or {}
    if metadata.get("agp_owner_activation_completed") is True:
        ensure_owner_profile()
        return {"status": "already_activated", "message": "Acesso proprietário já ativado e perfil validado"}

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
        _user_url(user_id),
        headers=_admin_headers(),
        json={
            "password": payload.new_password,
            "email_confirm": True,
            "user_metadata": metadata,
        },
        timeout=20,
    )
    if update_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível concluir a ativação")

    ensure_owner_profile()
    return {"status": "activated", "message": "Acesso proprietário ativado com sucesso"}


@router.post("/repair-profile")
def repair_owner_profile():
    return ensure_owner_profile()
