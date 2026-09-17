from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant
from app.canonical_professional_assessment import _authorize_professional

router = APIRouter(prefix="/api/v1", tags=["canonical-professional-validation"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _result(resultado_id: UUID) -> dict[str, Any]:
    row = _first(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
        "id": f"eq.{resultado_id}",
        "select": "id,atleta_id,projeto_id,tipo,versao_motor,protocolo_id,resultado,explicacao,confianca,limitacoes,status,created_at",
        "limit": "1",
    }))
    if not row:
        raise HTTPException(status_code=404, detail="Resultado analítico não encontrado")
    if not row.get("projeto_id"):
        raise HTTPException(status_code=422, detail="Resultado analítico sem projeto canônico associado")
    return row


def _participant_from_result(result: dict[str, Any]) -> dict[str, Any]:
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "legacy_perfil_atleta_id": f"eq.{result['atleta_id']}",
        "status": "eq.ativo",
        "select": "pessoa_id",
        "limit": "1",
    }))
    if not profile:
        raise HTTPException(status_code=422, detail="Resultado analítico não reconciliado com pessoa canônica")
    participant = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "pessoa_id": f"eq.{profile['pessoa_id']}",
        "projeto_id": f"eq.{result['projeto_id']}",
        "funcao_no_projeto": "eq.atleta",
        "ativo": "eq.true",
        "select": "id,pessoa_id,projeto_id,funcao_no_projeto",
        "limit": "1",
    }))
    if not participant:
        raise HTTPException(status_code=422, detail="Resultado analítico não reconciliado com participante canônico")
    return participant


class CanonicalProfessionalValidationInput(BaseModel):
    dominio: str = Field(min_length=2, max_length=80)
    decisao: str = Field(regex="^(aprovado|rejeitado|substituido)$")
    parecer_tecnico: str = Field(min_length=10, max_length=5000)
    evidencias: list[dict[str, Any]] = Field(default_factory=list)
    visivel_atleta: bool = False
    visivel_comissao: bool = True
    visivel_instituicao: bool = True
    substitui_resultado_id: UUID | None = None
    motivo_substituicao: str | None = Field(default=None, max_length=3000)


@router.get("/resultados/{resultado_id}/validacoes-canonicas")
def list_canonical_validations(
    resultado_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    result = _result(resultado_id)
    participant = _participant_from_result(result)
    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]):
        contexts = _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
            "pessoa_id": f"eq.{actor['pessoa_id']}",
            "projeto_id": f"eq.{participant['projeto_id']}",
            "status": "eq.ativo",
            "select": "papel_codigo",
            "limit": "1",
        }))
        if not contexts:
            raise HTTPException(status_code=403, detail="Sem vínculo ativo com o projeto do atleta")
    validations = _rows(_request("GET", "/rest/v1/agp_validacoes_profissionais_canonicas", params={
        "resultado_id": f"eq.{resultado_id}",
        "select": "*",
        "order": "created_at.desc",
    }))
    return {
        "modelo": "AGP-Professional-Validation-v1",
        "resultado_id": str(resultado_id),
        "validacoes": validations,
        "principio": "resultado_analitico_so_adquire_significado_profissional_dentro_de_competencia_autorizada",
    }


@router.post("/resultados/{resultado_id}/validacoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_canonical_validation(
    resultado_id: UUID,
    payload: CanonicalProfessionalValidationInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    result = _result(resultado_id)
    participant = _participant_from_result(result)
    scope = _authorize_professional(str(actor["pessoa_id"]), participant, payload.dominio)

    if payload.decisao == "substituido" and not payload.substitui_resultado_id:
        raise HTTPException(status_code=422, detail="Resultado substituto é obrigatório quando a decisão for substituído")
    if payload.decisao != "substituido" and payload.substitui_resultado_id:
        raise HTTPException(status_code=422, detail="Resultado substituto só deve ser informado quando a decisão for substituído")

    if payload.substitui_resultado_id:
        replacement = _result(payload.substitui_resultado_id)
        if str(replacement.get("projeto_id")) != str(result.get("projeto_id")):
            raise HTTPException(status_code=422, detail="Resultado substituto pertence a outro projeto")
        replacement_participant = _participant_from_result(replacement)
        if str(replacement_participant["id"]) != str(participant["id"]):
            raise HTTPException(status_code=422, detail="Resultado substituto pertence a outro atleta")

    created = _first(_request("POST", "/rest/v1/agp_validacoes_profissionais", payload={
        "resultado_id": str(resultado_id),
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "decisao": payload.decisao,
        "parecer_tecnico": payload.parecer_tecnico,
        "papel_profissional": scope["papel_codigo"],
        "competencia_codigo": scope["competencia_codigo"],
        "credencial_verificada_no_registro": scope["credencial_verificada"],
        "natureza_validacao": "profissional_competencia_canonica",
        "evidencia_referencia": payload.evidencias,
        "profissional_auth_id": str(user["id"]),
        "visivel_atleta": payload.visivel_atleta,
        "visivel_comissao": payload.visivel_comissao,
        "visivel_instituicao": payload.visivel_instituicao,
        "substitui_resultado_id": str(payload.substitui_resultado_id) if payload.substitui_resultado_id else None,
        "motivo_substituicao": payload.motivo_substituicao,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar validação profissional canônica")

    _request("PATCH", "/rest/v1/agp_resultados_analiticos", params={"id": f"eq.{resultado_id}"}, payload={
        "status": "validado" if payload.decisao == "aprovado" else "rejeitado" if payload.decisao == "rejeitado" else "substituido",
        "validado_por_auth_id": str(user["id"]),
        "parecer_tecnico": payload.parecer_tecnico,
        "decisao_profissional": payload.decisao,
        "papel_validador": scope["papel_codigo"],
        "visivel_atleta": payload.visivel_atleta,
        "visivel_comissao": payload.visivel_comissao,
        "visivel_instituicao": payload.visivel_instituicao,
        "substitui_resultado_id": str(payload.substitui_resultado_id) if payload.substitui_resultado_id else None,
        "motivo_substituicao": payload.motivo_substituicao,
    })

    return {
        "validacao": created,
        "escopo_profissional": scope,
        "resultado": {
            "id": str(resultado_id),
            "tipo": result.get("tipo"),
            "versao_motor": result.get("versao_motor"),
        },
        "nao_significa": ["verdade_clinica_automatica", "competencia_fora_do_escopo", "causalidade_automatica"],
    }
