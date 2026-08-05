from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["baseline-management"])


class BaselineInput(BaseModel):
    categoria: str = Field(min_length=1, max_length=120)
    idade_cronologica: float = Field(gt=0, le=120)
    sexo_registrado: str = Field(min_length=1, max_length=40)
    modalidade: str = Field(min_length=2, max_length=120)
    prova_posicao: str | None = Field(default=None, max_length=120)
    estagio_maturacional: str | None = Field(default=None, max_length=120)
    altura_cm: float = Field(gt=30, le=260)
    massa_kg: float = Field(gt=5, le=400)
    envergadura_cm: float | None = Field(default=None, gt=30, le=300)
    data_referencia: date
    origem: str = Field(min_length=2, max_length=120)
    observacoes: str | None = Field(default=None, max_length=2000)
    validar: bool = False


def _participant_context(participante_id: UUID) -> dict[str, Any]:
    rows = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}", "select": "id,pessoa_id,projeto_id,funcao_no_projeto,ativo"},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    participant = rows[0]
    if participant.get("funcao_no_projeto") != "atleta" or not participant.get("ativo"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Linha de base exige participante atleta ativo")

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
    value = calculated if isinstance(calculated, str) else "linha_base_pendente"
    _request(
        "PATCH",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}"},
        payload={"status_onboarding": value, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return value


@router.get("/projetos/{projeto_id}/linhas-base")
def list_baselines(projeto_id: UUID, authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_status_linhas_base",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "nome.asc"},
    )
    return rows if isinstance(rows, list) else []


@router.post("/participantes/{participante_id}/linha-base", status_code=status.HTTP_201_CREATED)
def upsert_baseline(
    participante_id: UUID,
    payload: BaselineInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    context = _participant_context(participante_id)

    _request(
        "PATCH",
        "/rest/v1/agp_linhas_base_atleta",
        params={
            "atleta_id": f"eq.{context['atleta_id']}",
            "projeto_id": f"eq.{context['projeto_id']}",
            "status": "in.(completa,validada)",
        },
        payload={"status": "substituida", "updated_at": datetime.now(timezone.utc).isoformat()},
    )

    row = _single_row(
        _request(
            "POST",
            "/rest/v1/agp_linhas_base_atleta",
            payload={
                "participante_id": str(participante_id),
                "atleta_id": context["atleta_id"],
                "projeto_id": context["projeto_id"],
                "categoria": payload.categoria,
                "idade_cronologica": payload.idade_cronologica,
                "sexo_registrado": payload.sexo_registrado,
                "modalidade": payload.modalidade,
                "prova_posicao": payload.prova_posicao,
                "estagio_maturacional": payload.estagio_maturacional,
                "altura_cm": payload.altura_cm,
                "massa_kg": payload.massa_kg,
                "envergadura_cm": payload.envergadura_cm,
                "data_referencia": payload.data_referencia.isoformat(),
                "origem": payload.origem,
                "responsavel_auth_id": str(operator_id),
                "observacoes": payload.observacoes,
                "status": "validada" if payload.validar else "completa",
                "validado_por_auth_id": str(operator_id) if payload.validar else None,
                "validado_em": datetime.now(timezone.utc).isoformat() if payload.validar else None,
            },
        ),
        "linha de base",
    )

    onboarding_status = _refresh_onboarding(participante_id)
    _request(
        "POST",
        "/rest/v1/agp_auditoria_participantes",
        payload={
            "pessoa_id": context["pessoa_id"],
            "projeto_id": context["projeto_id"],
            "acao": "linha_base_registrada",
            "estado_novo": {
                "linha_base_id": row["id"],
                "status": row.get("status"),
                "completude": row.get("completude"),
                "status_onboarding": onboarding_status,
            },
            "executado_por": str(operator_id),
            "origem": "api_baseline_v1",
        },
    )
    return {
        "linha_base_id": row["id"],
        "participante_id": str(participante_id),
        "status": row.get("status"),
        "completude": row.get("completude"),
        "status_onboarding": onboarding_status,
    }
