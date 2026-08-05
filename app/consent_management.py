from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["consent-management"])


class ConsentGrant(BaseModel):
    finalidade: str = Field(default="monitoramento_esportivo", min_length=3, max_length=160)
    versao_termo: str = Field(min_length=1, max_length=40)
    tipo_consentimento: str = Field(default="tratamento_dados_esportivos", min_length=3, max_length=120)
    escopo: dict[str, Any] = Field(default_factory=dict)
    responsavel_legal_auth_id: UUID | None = None
    hash_termo: str | None = Field(default=None, max_length=256)


class ConsentResponse(BaseModel):
    consentimento_id: UUID
    participante_id: UUID
    atleta_id: UUID
    projeto_id: UUID
    vigente: bool
    concedido_em: datetime


def _participant_context(participante_id: UUID) -> dict[str, Any]:
    participants = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}", "select": "id,pessoa_id,projeto_id,funcao_no_projeto,ativo"},
    )
    if not participants:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    participant = participants[0]
    if participant.get("funcao_no_projeto") != "atleta" or not participant.get("ativo"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Consentimento operacional exige participante atleta ativo")

    profiles = _request(
        "GET",
        "/rest/v1/agp_perfis_esportivos",
        params={"pessoa_id": f"eq.{participant['pessoa_id']}", "select": "legacy_perfil_atleta_id"},
    )
    athlete_id = profiles[0].get("legacy_perfil_atleta_id") if profiles else None
    if not athlete_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Atleta ainda não possui vínculo legado necessário ao núcleo de evidências")

    return {**participant, "atleta_id": athlete_id}


def _refresh_onboarding(participante_id: UUID) -> str:
    calculated = _request(
        "POST",
        "/rest/v1/rpc/agp_status_onboarding_participante",
        payload={"p_participante_id": str(participante_id)},
    )
    status_value = calculated if isinstance(calculated, str) else "consentimento_pendente"
    _request(
        "PATCH",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}"},
        payload={"status_onboarding": status_value, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return status_value


@router.get("/projetos/{projeto_id}/consentimentos")
def list_consents(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_status_consentimentos",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "nome.asc"},
    )
    return rows if isinstance(rows, list) else []


@router.post(
    "/participantes/{participante_id}/consentimentos",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_consent(
    participante_id: UUID,
    payload: ConsentGrant,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ConsentResponse:
    operator_id = _require_owner(authorization)
    context = _participant_context(participante_id)
    now = datetime.now(timezone.utc)

    _request(
        "PATCH",
        "/rest/v1/agp_consentimentos",
        params={
            "atleta_id": f"eq.{context['atleta_id']}",
            "projeto_id": f"eq.{context['projeto_id']}",
            "finalidade": f"eq.{payload.finalidade}",
            "revogado_em": "is.null",
        },
        payload={"revogado_em": now.isoformat()},
    )

    row = _single_row(
        _request(
            "POST",
            "/rest/v1/agp_consentimentos",
            payload={
                "atleta_id": context["atleta_id"],
                "projeto_id": context["projeto_id"],
                "participante_id": str(participante_id),
                "responsavel_legal_auth_id": str(payload.responsavel_legal_auth_id) if payload.responsavel_legal_auth_id else None,
                "concedido_por_auth_id": str(operator_id),
                "finalidade": payload.finalidade,
                "versao_termo": payload.versao_termo,
                "tipo_consentimento": payload.tipo_consentimento,
                "concedido_em": now.isoformat(),
                "escopo": payload.escopo,
                "hash_termo": payload.hash_termo,
                "ip_origem": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        ),
        "consentimento",
    )

    onboarding_status = _refresh_onboarding(participante_id)
    _request(
        "POST",
        "/rest/v1/agp_auditoria_participantes",
        payload={
            "pessoa_id": context["pessoa_id"],
            "projeto_id": context["projeto_id"],
            "acao": "consentimento_concedido",
            "estado_novo": {
                "consentimento_id": row["id"],
                "finalidade": payload.finalidade,
                "versao_termo": payload.versao_termo,
                "status_onboarding": onboarding_status,
            },
            "executado_por": str(operator_id),
            "origem": "api_consent_v1",
        },
    )

    return ConsentResponse(
        consentimento_id=UUID(row["id"]),
        participante_id=participante_id,
        atleta_id=UUID(context["atleta_id"]),
        projeto_id=UUID(context["projeto_id"]),
        vigente=True,
        concedido_em=now,
    )


@router.post("/consentimentos/{consentimento_id}/revogar")
def revoke_consent(
    consentimento_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_consentimentos",
        params={"id": f"eq.{consentimento_id}", "select": "id,participante_id,atleta_id,projeto_id,revogado_em"},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consentimento não encontrado")
    consent = rows[0]
    if consent.get("revogado_em"):
        return {"consentimento_id": str(consentimento_id), "vigente": False, "status": "ja_revogado"}

    revoked_at = datetime.now(timezone.utc)
    _request(
        "PATCH",
        "/rest/v1/agp_consentimentos",
        params={"id": f"eq.{consentimento_id}"},
        payload={"revogado_em": revoked_at.isoformat()},
    )
    participant_id = consent.get("participante_id")
    onboarding_status = _refresh_onboarding(UUID(participant_id)) if participant_id else "consentimento_pendente"

    _request(
        "POST",
        "/rest/v1/agp_auditoria_participantes",
        payload={
            "projeto_id": consent.get("projeto_id"),
            "acao": "consentimento_revogado",
            "estado_novo": {
                "consentimento_id": str(consentimento_id),
                "revogado_em": revoked_at.isoformat(),
                "status_onboarding": onboarding_status,
            },
            "executado_por": str(operator_id),
            "origem": "api_consent_v1",
        },
    )
    return {"consentimento_id": str(consentimento_id), "vigente": False, "revogado_em": revoked_at.isoformat()}
