from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["professional-validation"])


class ProfessionalValidationInput(BaseModel):
    decisao: str = Field(regex="^(aprovado|rejeitado|substituido)$")
    parecer_tecnico: str = Field(min_length=10, max_length=5000)
    papel_profissional: str = Field(min_length=2, max_length=80)
    visivel_atleta: bool = False
    visivel_comissao: bool = True
    visivel_instituicao: bool = True
    substitui_resultado_id: UUID | None = None
    motivo_substituicao: str | None = None


@router.get("/projetos/{projeto_id}/resultados-profissionais")
def list_professional_results(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_resultados_profissionais_operacionais",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "created_at.desc"},
    )
    return rows if isinstance(rows, list) else []


@router.post("/resultados/{resultado_id}/validacoes", status_code=status.HTTP_201_CREATED)
def validate_result(
    resultado_id: UUID,
    payload: ProfessionalValidationInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    results = _request(
        "GET",
        "/rest/v1/agp_resultados_analiticos",
        params={"id": f"eq.{resultado_id}", "select": "id,status,projeto_id"},
    )
    if not results:
        raise HTTPException(status_code=404, detail="Resultado analítico não encontrado")
    if payload.decisao == "substituido" and not payload.substitui_resultado_id:
        raise HTTPException(status_code=422, detail="Informe o resultado substituto")

    return _single_row(
        _request(
            "POST",
            "/rest/v1/agp_validacoes_profissionais",
            payload={
                "resultado_id": str(resultado_id),
                "decisao": payload.decisao,
                "parecer_tecnico": payload.parecer_tecnico,
                "papel_profissional": payload.papel_profissional,
                "profissional_auth_id": str(owner_id),
                "visivel_atleta": payload.visivel_atleta,
                "visivel_comissao": payload.visivel_comissao,
                "visivel_instituicao": payload.visivel_instituicao,
                "substitui_resultado_id": str(payload.substitui_resultado_id) if payload.substitui_resultado_id else None,
                "motivo_substituicao": payload.motivo_substituicao,
            },
        ),
        "validação profissional",
    )


@router.get("/resultados/{resultado_id}/validacoes")
def list_result_validations(
    resultado_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_validacoes_profissionais",
        params={"resultado_id": f"eq.{resultado_id}", "select": "*", "order": "created_at.desc"},
    )
    return rows if isinstance(rows, list) else []
