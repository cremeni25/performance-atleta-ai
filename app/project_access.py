from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.participant_onboarding import _request
from app.supabase_client import SUPABASE_KEY


def require_project_professional(authorization: str | None, project_id: UUID) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso ausente")

    token = authorization.split(" ", 1)[1].strip()
    auth_headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    user = _request("GET", "/auth/v1/user", headers=auth_headers)
    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

    allowed = _request(
        "POST",
        "/rest/v1/rpc/agp_profissional_pode_projeto",
        payload={"p_projeto_id": str(project_id)},
        headers=auth_headers,
    )
    if allowed is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso profissional não autorizado para este projeto")
    return UUID(user_id)
