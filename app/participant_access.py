from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["participant-access"])


@router.post("/participantes/{participante_id}/convidar-acesso")
def invite_participant_access(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)

    participants = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={
            "id": f"eq.{participante_id}",
            "select": "id,pessoa_id,projeto_id,funcao_no_projeto,ativo,status_onboarding",
        },
    )
    if not participants:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    participant = participants[0]
    if participant.get("ativo") is not True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Participante inativo")

    accounts = _request(
        "GET",
        "/rest/v1/agp_contas_acesso",
        params={
            "pessoa_id": f"eq.{participant['pessoa_id']}",
            "select": "id,pessoa_id,auth_id,email_acesso,status",
        },
    )
    if not accounts:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Participante sem conta de acesso cadastrada")
    account = accounts[0]

    if account.get("auth_id"):
        return {
            "status": "acesso_ja_vinculado",
            "participante_id": str(participante_id),
            "conta_id": account.get("id"),
        }

    email = str(account.get("email_acesso") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Conta sem e-mail de acesso")

    invited = _request(
        "POST",
        "/auth/v1/invite",
        payload={
            "email": email,
            "data": {
                "agp_participante_id": str(participante_id),
                "agp_pessoa_id": str(participant["pessoa_id"]),
            },
        },
    )

    auth_id = invited.get("id") if isinstance(invited, dict) else None
    if not auth_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Supabase Auth não retornou o usuário convidado")

    linked = _single_row(
        _request(
            "PATCH",
            "/rest/v1/agp_contas_acesso",
            params={"id": f"eq.{account['id']}", "auth_id": "is.null"},
            payload={"auth_id": auth_id},
        ),
        "vínculo de acesso",
    )

    _request(
        "POST",
        "/rest/v1/agp_auditoria_participantes",
        payload={
            "pessoa_id": participant["pessoa_id"],
            "projeto_id": participant.get("projeto_id"),
            "acao": "convite_acesso_enviado",
            "estado_anterior": {"status": account.get("status"), "auth_id": None},
            "estado_novo": {"status": account.get("status"), "auth_id": auth_id},
            "executado_por": str(operator_id),
            "origem": "api_participant_access_v1",
        },
    )

    return {
        "status": "convite_enviado",
        "participante_id": str(participante_id),
        "conta_id": linked.get("id"),
        "auth_id": auth_id,
    }
