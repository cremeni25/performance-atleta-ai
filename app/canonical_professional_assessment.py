from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant

router = APIRouter(prefix="/api/v1", tags=["canonical-professional-assessment"])

REGULATED_COMPETENCES = {
    "medicine.clinical",
    "nutrition.sport",
    "physiology.exercise",
    "physiotherapy.msk_rehab",
    "psychology.sport",
}

DOMAIN_RULES: dict[str, dict[str, set[str]]] = {
    "fisico": {"competencias": {"strength_conditioning"}, "capacidades": {"assessment.physical"}},
    "fisiologico": {"competencias": {"physiology.exercise"}, "capacidades": {"assessment.physiology"}},
    "biologico": {"competencias": {"physiology.exercise", "medicine.clinical"}, "capacidades": {"assessment.physiology", "assessment.medical"}},
    "tecnico": {"competencias": {"swimming.coaching", "swimming.technical_analysis"}, "capacidades": {"evidence.review_technical", "analysis.performance", "decision.technical"}},
    "mental": {"competencias": {"psychology.sport"}, "capacidades": {"assessment.psychology"}},
    "psicologico": {"competencias": {"psychology.sport"}, "capacidades": {"assessment.psychology"}},
    "medico": {"competencias": {"medicine.clinical"}, "capacidades": {"assessment.medical"}},
    "recuperacao": {"competencias": {"strength_conditioning", "physiotherapy.msk_rehab", "physiology.exercise"}, "capacidades": {"assessment.physical", "assessment.physiotherapy", "assessment.physiology"}},
    "contextual": {"competencias": {"performance.analysis", "swimming.coaching"}, "capacidades": {"analysis.performance", "evidence.review_technical"}},
    "crescimento": {"competencias": {"physiology.exercise", "medicine.clinical"}, "capacidades": {"assessment.physiology", "assessment.medical"}},
    "maturacao": {"competencias": {"physiology.exercise", "medicine.clinical"}, "capacidades": {"assessment.physiology", "assessment.medical"}},
    "nutricional": {"competencias": {"nutrition.sport"}, "capacidades": {"assessment.nutrition"}},
    "fisioterapia": {"competencias": {"physiotherapy.msk_rehab"}, "capacidades": {"assessment.physiotherapy"}},
}


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _contexts(pessoa_id: str, projeto_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "projeto_id": f"eq.{projeto_id}",
        "status": "eq.ativo",
        "select": "papel_codigo,capacidades,competencias",
    }))


def _authorize_professional(actor_pessoa_id: str, participant: dict[str, Any], domain: str) -> dict[str, Any]:
    rule = DOMAIN_RULES.get(domain)
    if not rule:
        raise HTTPException(status_code=422, detail="Domínio profissional não reconhecido pelo modelo canônico")
    contexts = _contexts(actor_pessoa_id, str(participant.get("projeto_id") or ""))
    if not contexts:
        raise HTTPException(status_code=403, detail="Profissional sem vínculo ativo com o projeto")

    for context in contexts:
        capabilities = {
            item.get("codigo") for item in (context.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
        if not capabilities.intersection(rule["capacidades"]):
            continue
        for competence in (context.get("competencias") or []):
            if not isinstance(competence, dict):
                continue
            code = competence.get("codigo")
            if code not in rule["competencias"]:
                continue
            requires_credential = code in REGULATED_COMPETENCES or bool(competence.get("requer_credencial_regulada"))
            verified = bool(competence.get("credencial_verificada"))
            if requires_credential and not verified:
                continue
            return {
                "papel_codigo": context.get("papel_codigo"),
                "competencia_codigo": code,
                "credencial_verificada": verified,
                "requer_credencial": requires_credential,
            }
    raise HTTPException(status_code=403, detail="Papel/competência profissional insuficiente ou credencial regulada não verificada")


def _legacy_athlete_id(pessoa_id: str) -> str | None:
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{pessoa_id}", "status": "eq.ativo",
        "select": "legacy_perfil_atleta_id", "limit": "1",
    }))
    return str(profile["legacy_perfil_atleta_id"]) if profile and profile.get("legacy_perfil_atleta_id") else None


class ProfessionalAssessmentCreate(BaseModel):
    dominio: str = Field(min_length=2, max_length=80)
    instrumento_referencia: str | None = Field(default=None, max_length=240)
    metricas: dict[str, Any] = Field(default_factory=dict)
    achados: list[Any] = Field(default_factory=list)
    restricoes: list[Any] = Field(default_factory=list)
    recomendacoes: list[Any] = Field(default_factory=list)
    evidencias: list[dict[str, Any]] = Field(default_factory=list)
    confianca: float | None = Field(default=None, ge=0, le=100)
    validade_ate: datetime | None = None
    ciclo_id: UUID | None = None


@router.get("/participantes/{participante_id}/avaliacoes-profissionais-canonicas")
def list_assessments(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    contexts = _contexts(str(actor["pessoa_id"]), str(participant.get("projeto_id") or ""))
    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]) and not contexts:
        raise HTTPException(status_code=403, detail="Sem vínculo ativo com o projeto do atleta")
    rows = _rows(_request("GET", "/rest/v1/agp_avaliacoes_profissionais_canonicas", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "data_avaliacao.desc", "limit": "100",
    }))
    return {
        "modelo": "AGP-Professional-Assessment-v1",
        "participante_id": str(participante_id),
        "avaliacoes": rows,
        "principio": "competencia_profissional_evidencia_contexto",
    }


@router.post("/participantes/{participante_id}/avaliacoes-profissionais-canonicas", status_code=status.HTTP_201_CREATED)
def create_assessment(participante_id: UUID, payload: ProfessionalAssessmentCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _authorize_professional(str(actor["pessoa_id"]), participant, payload.dominio)
    now = datetime.now(timezone.utc).isoformat()
    created = _first(_request("POST", "/rest/v1/agp_avaliacoes_profissionais", payload={
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "atleta_id": _legacy_athlete_id(str(participant["pessoa_id"])),
        "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None,
        "dominio": payload.dominio,
        "papel_profissional": scope["papel_codigo"],
        "competencia_codigo": scope["competencia_codigo"],
        "credencial_verificada_no_registro": scope["credencial_verificada"],
        "natureza_avaliacao": "profissional_competencia_canonica",
        "profissional_auth_id": str(user["id"]),
        "data_avaliacao": now,
        "validade_ate": payload.validade_ate.isoformat() if payload.validade_ate else None,
        "instrumento_referencia": payload.instrumento_referencia,
        "metricas": payload.metricas,
        "achados": payload.achados,
        "restricoes": payload.restricoes,
        "recomendacoes": payload.recomendacoes,
        "evidencia_referencia": payload.evidencias,
        "confianca": payload.confianca,
        "status": "validada",
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar avaliação profissional canônica")
    return {
        "avaliacao": created,
        "escopo_profissional": scope,
        "nao_significa": ["diagnostico_automatico_por_ia", "competencia_fora_do_escopo_profissional"],
    }
