import os
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
OWNER_EMAIL = "anderson@cremeni.com.br"

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class UserInviteRequest(BaseModel):
    nome: str
    email: str
    tipo_usuario: str
    instituicao: str | None = None
    dias_acesso: int = 30


def _headers():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Serviço administrativo não configurado.")
    return {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _require_owner(authorization: str | None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão administrativa ausente.")
    token = authorization.split(" ", 1)[1]
    response = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"apikey": SERVICE_ROLE_KEY, "Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Sessão administrativa inválida.")
    user = response.json()
    metadata = user.get("user_metadata") or {}
    email = str(user.get("email") or "").strip().lower()
    if email != OWNER_EMAIL and metadata.get("is_owner") is not True:
        raise HTTPException(status_code=403, detail="Acesso exclusivo do proprietário Master.")


@router.post("/invite")
def invite_user(payload: UserInviteRequest, authorization: str | None = Header(default=None)):
    _require_owner(authorization)

    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="E-mail inválido.")

    allowed = {"atleta", "comissao", "clube", "master"}
    if payload.tipo_usuario not in allowed:
        raise HTTPException(status_code=400, detail="Perfil de acesso inválido.")

    redirect_to = os.getenv("AGP_FRONTEND_URL", "https://agp-frontend-vite.onrender.com").rstrip("/") + "/redefinir-senha"
    invite = requests.post(
        f"{SUPABASE_URL}/auth/v1/invite",
        headers=_headers(),
        params={"redirect_to": redirect_to},
        json={
            "email": email,
            "data": {
                "nome": payload.nome.strip(),
                "tipo_usuario": payload.tipo_usuario,
                "funcao": payload.tipo_usuario,
                "instituicao": payload.instituicao,
                "is_owner": payload.tipo_usuario == "master",
            },
        },
        timeout=25,
    )

    if invite.status_code >= 400:
        detail = invite.json().get("msg") if invite.headers.get("content-type", "").startswith("application/json") else invite.text
        raise HTTPException(status_code=400, detail=detail or "Não foi possível enviar o convite.")

    user = invite.json()
    auth_id = user.get("id")
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(payload.dias_acesso, 365)))

    profile_payload = {
        "auth_id": auth_id,
        "nome": payload.nome.strip(),
        "email": email,
        "tipo_usuario": payload.tipo_usuario,
        "funcao": payload.tipo_usuario,
        "instituicao": payload.instituicao,
        "status": "convidado",
        "ativo": True,
        "acesso_expira_em": expires_at.isoformat(),
    }
    profile = requests.post(
        f"{SUPABASE_URL}/rest/v1/perfis_atletas",
        headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
        params={"on_conflict": "auth_id"},
        json=profile_payload,
        timeout=25,
    )
    if profile.status_code >= 400:
        raise HTTPException(status_code=500, detail="Convite enviado, mas o perfil institucional não foi concluído.")

    return {
        "status": "convite_enviado",
        "email": email,
        "tipo_usuario": payload.tipo_usuario,
        "acesso_expira_em": expires_at.isoformat(),
    }
