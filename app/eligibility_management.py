from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1", tags=["eligibility-management"])


@router.get("/projetos/{projeto_id}/elegibilidade")
def list_project_eligibility(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_elegibilidade_operacional_projeto",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "nome.asc"},
    )
    return rows if isinstance(rows, list) else []


@router.get("/participantes/{participante_id}/elegibilidade")
def get_participant_eligibility(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_owner(authorization)
    result = _request(
        "POST",
        "/rest/v1/rpc/agp_elegibilidade_operacional",
        payload={"p_participante_id": str(participante_id)},
    )
    return result if isinstance(result, dict) else {
        "participante_id": str(participante_id),
        "apto_coleta": False,
        "apto_analise": False,
        "pendencias": ["elegibilidade_indisponivel"],
    }
