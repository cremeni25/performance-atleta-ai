from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant

router = APIRouter(prefix="/api/v1", tags=["canonical-decision-cycle"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _contexts(actor_pessoa_id: str, project_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
        "pessoa_id": f"eq.{actor_pessoa_id}", "projeto_id": f"eq.{project_id}", "status": "eq.ativo",
        "select": "papel_codigo,familia,capacidades,competencias",
    }))


def _authorize_write(actor_pessoa_id: str, participant: dict[str, Any], domain: str) -> dict[str, Any]:
    project_id = str(participant.get("projeto_id") or "")
    contexts = _contexts(actor_pessoa_id, project_id)
    capabilities = {
        item.get("codigo") for row in contexts for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }
    competences = {
        item.get("codigo"): item for row in contexts for item in (row.get("competencias") or [])
        if isinstance(item, dict) and item.get("codigo")
    }
    if "platform.govern" in capabilities:
        return {"papel_codigo": "master_governance", "competencia_codigo": None, "modo": "governanca"}

    regulated = {
        "medico": "medicine.clinical",
        "psicologico": "psychology.sport",
        "nutricional": "nutrition.sport",
        "fisiologia": "physiology.exercise",
        "fisiologico": "physiology.exercise",
        "fisioterapia": "physiotherapy.msk_rehab",
    }
    required = regulated.get(domain)
    if required:
        competence = competences.get(required)
        if not competence or not competence.get("credencial_verificada"):
            raise HTTPException(status_code=403, detail="Domínio regulado exige competência e credencial profissional verificadas")
        role = next((row.get("papel_codigo") for row in contexts if any(isinstance(c, dict) and c.get("codigo") == required for c in (row.get("competencias") or []))), None)
        return {"papel_codigo": role, "competencia_codigo": required, "modo": "profissional_regulado"}

    allowed = {"decision.technical", "training.plan", "analysis.performance", "evidence.review_technical"}
    if not capabilities.intersection(allowed):
        raise HTTPException(status_code=403, detail="Papel atual não possui capacidade para decisão operacional deste atleta")
    role = contexts[0].get("papel_codigo") if contexts else None
    competence_code = next(iter(competences.keys()), None)
    return {"papel_codigo": role, "competencia_codigo": competence_code, "modo": "profissional_projeto"}


class EvidenceRef(BaseModel):
    tipo_evidencia: Literal["coleta", "metrica_observada", "serie_longitudinal", "sessao", "competicao", "avaliacao_profissional", "resultado_analitico", "marco", "intervencao_anterior", "resposta_anterior", "fonte_cientifica", "contexto"]
    referencia_id: UUID | None = None
    referencia_codigo: str | None = None
    papel: Literal["suporte", "limitacao", "contradicao", "contexto"] = "suporte"
    resumo: dict[str, Any] = Field(default_factory=dict)


class DecisionCreate(BaseModel):
    dominio: str = Field(min_length=2, max_length=80)
    tipo: Literal["tecnica", "treino", "recuperacao", "competicao", "saude", "psicologia", "nutricao", "disponibilidade", "outra"]
    decisao: str = Field(min_length=5, max_length=5000)
    justificativa: str = Field(min_length=5, max_length=5000)
    ciclo_id: UUID | None = None
    evidencias: list[EvidenceRef] = Field(min_length=1)
    exige_validacao_profissional: bool = False
    dominio_validacao: str | None = None


class InterventionCreate(BaseModel):
    dominio: str = Field(min_length=2, max_length=80)
    descricao: str = Field(min_length=5, max_length=5000)
    justificativa: str = Field(min_length=5, max_length=5000)
    resultado_esperado: dict[str, Any] = Field(default_factory=dict)
    ciclo_id: UUID | None = None
    fim_previsto: datetime | None = None
    status: Literal["proposta", "aprovada", "em_execucao"] = "proposta"


class ResponseCreate(BaseModel):
    estado_comparabilidade: Literal["comparavel", "dados_insuficientes", "nao_comparavel", "revisao_requerida"]
    metricas_antes: dict[str, Any] = Field(default_factory=dict)
    metricas_depois: dict[str, Any] = Field(default_factory=dict)
    variacoes: dict[str, Any] = Field(default_factory=dict)
    conclusao: str = Field(min_length=5, max_length=5000)
    classificacao_profissional: Literal["favoravel", "neutra", "desfavoravel", "inconclusiva"] | None = None
    confianca: float | None = Field(default=None, ge=0, le=100)
    ciclo_id: UUID | None = None


class LearningCreate(BaseModel):
    tipo: Literal["fato", "padrao_observado", "hipotese", "limitacao", "resposta_a_intervencao", "nao_comparavel"]
    descricao: str = Field(min_length=5, max_length=5000)
    evidencias: list[dict[str, Any]] = Field(default_factory=list)
    confianca: float | None = Field(default=None, ge=0, le=1)
    status: Literal["registrado", "revisao_profissional", "validado"] = "registrado"


@router.get("/participantes/{participante_id}/ciclo-decisao-canonico")
def get_cycle(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    project_id = str(participant.get("projeto_id") or "")
    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]) and not _contexts(str(actor["pessoa_id"]), project_id):
        raise HTTPException(status_code=403, detail="Sem vínculo ativo com o projeto do atleta")
    cycles = _rows(_request("GET", "/rest/v1/agp_ciclo_decisao_canonico", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "decisao_em.desc"
    }))
    return {
        "modelo": "AGP-Decision-Intervention-Response-Learning-v1",
        "participante_id": str(participante_id),
        "ciclos": cycles,
        "principio": "evidencia_decisao_intervencao_resposta_aprendizado",
        "legado_score_global_necessario": False,
    }


@router.post("/participantes/{participante_id}/decisoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_decision(participante_id: UUID, payload: DecisionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _authorize_write(str(actor["pessoa_id"]), participant, payload.dominio)
    for ev in payload.evidencias:
        if not ev.referencia_id and not ev.referencia_codigo:
            raise HTTPException(status_code=422, detail="Cada evidência precisa de referencia_id ou referencia_codigo")
    decision = _first(_request("POST", "/rest/v1/agp_decisoes_canonicas", payload={
        "pessoa_id": participant["pessoa_id"], "participante_id": str(participante_id), "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None, "dominio": payload.dominio, "tipo": payload.tipo,
        "decisao": payload.decisao, "justificativa": payload.justificativa, "decidido_por_pessoa_id": actor["pessoa_id"],
        "papel_codigo": scope.get("papel_codigo"), "competencia_codigo": scope.get("competencia_codigo"),
        "exige_validacao_profissional": payload.exige_validacao_profissional, "dominio_validacao": payload.dominio_validacao,
    }))
    if not decision:
        raise HTTPException(status_code=502, detail="Falha ao registrar decisão canônica")
    for ev in payload.evidencias:
        _request("POST", "/rest/v1/agp_decisao_evidencias", payload={
            "decisao_id": decision["id"], "tipo_evidencia": ev.tipo_evidencia,
            "referencia_id": str(ev.referencia_id) if ev.referencia_id else None,
            "referencia_codigo": ev.referencia_codigo, "papel": ev.papel, "resumo": ev.resumo,
        })
    return decision


@router.post("/decisoes-canonicas/{decisao_id}/intervencoes", status_code=status.HTTP_201_CREATED)
def create_intervention(decisao_id: UUID, payload: InterventionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    decision = _first(_request("GET", "/rest/v1/agp_decisoes_canonicas", params={"id": f"eq.{decisao_id}", "select": "*", "limit": "1"}))
    if not decision:
        raise HTTPException(status_code=404, detail="Decisão canônica não encontrada")
    participant = _target_participant(UUID(str(decision["participante_id"])))
    scope = _authorize_write(str(actor["pessoa_id"]), participant, payload.dominio)
    intervention = _first(_request("POST", "/rest/v1/agp_intervencoes", payload={
        "pessoa_id": participant["pessoa_id"], "participante_id": participant["id"], "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else decision.get("ciclo_id"), "decisao_id": str(decisao_id),
        "dominio": payload.dominio, "responsavel_auth_id": str(user["id"]), "papel_responsavel": scope.get("papel_codigo") or "canonical_role",
        "descricao": payload.descricao, "justificativa": payload.justificativa,
        "evidencia_origem": [{"decisao_id": str(decisao_id)}], "resultado_esperado": payload.resultado_esperado,
        "inicio": datetime.now(timezone.utc).isoformat(), "fim_previsto": payload.fim_previsto.isoformat() if payload.fim_previsto else None,
        "status": payload.status,
    }))
    if not intervention:
        raise HTTPException(status_code=502, detail="Falha ao registrar intervenção")
    _request("POST", "/rest/v1/agp_decisao_intervencoes", payload={"decisao_id": str(decisao_id), "intervencao_id": intervention["id"], "papel": "execucao"})
    return intervention


@router.post("/intervencoes/{intervencao_id}/respostas-canonicas", status_code=status.HTTP_201_CREATED)
def create_response(intervencao_id: UUID, payload: ResponseCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    intervention = _first(_request("GET", "/rest/v1/agp_intervencoes_canonicas", params={"id": f"eq.{intervencao_id}", "select": "*", "limit": "1"}))
    if not intervention or not intervention.get("participante_id"):
        raise HTTPException(status_code=404, detail="Intervenção canônica não encontrada")
    participant = _target_participant(UUID(str(intervention["participante_id"])))
    scope = _authorize_write(str(actor["pessoa_id"]), participant, str(intervention.get("dominio") or "tecnico"))
    legacy_class = {"favoravel": "melhora", "neutra": "neutra", "desfavoravel": "piora", "inconclusiva": "inconclusiva"}.get(payload.classificacao_profissional or "inconclusiva", "inconclusiva")
    response = _first(_request("POST", "/rest/v1/agp_respostas_intervencao", payload={
        "intervencao_id": str(intervencao_id), "participante_id": participant["id"], "pessoa_id": participant["pessoa_id"],
        "projeto_id": participant["projeto_id"], "avaliado_por_auth_id": str(user["id"]), "papel_avaliador": scope.get("papel_codigo") or "canonical_role",
        "data_avaliacao": datetime.now(timezone.utc).isoformat(), "metricas_antes": payload.metricas_antes, "metricas_depois": payload.metricas_depois,
        "variacoes": payload.variacoes, "classificacao_resposta": legacy_class, "classificacao_profissional": payload.classificacao_profissional,
        "estado_comparabilidade": payload.estado_comparabilidade, "significado_automatico": "mudanca_observada_sem_julgamento",
        "confianca": payload.confianca, "conclusao": payload.conclusao, "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else intervention.get("ciclo_id"),
        "visivel_atleta": True, "visivel_comissao": True, "visivel_instituicao": False,
    }))
    if not response:
        raise HTTPException(status_code=502, detail="Falha ao registrar resposta")
    return response


@router.post("/respostas-intervencao/{resposta_id}/aprendizados", status_code=status.HTTP_201_CREATED)
def create_learning(resposta_id: UUID, payload: LearningCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    response = _first(_request("GET", "/rest/v1/agp_respostas_intervencao", params={"id": f"eq.{resposta_id}", "select": "*", "limit": "1"}))
    if not response:
        raise HTTPException(status_code=404, detail="Resposta de intervenção não encontrada")
    participant = _target_participant(UUID(str(response["participante_id"])))
    _authorize_write(str(actor["pessoa_id"]), participant, "tecnico")
    intervention = _first(_request("GET", "/rest/v1/agp_intervencoes_canonicas", params={"id": f"eq.{response['intervencao_id']}", "select": "*", "limit": "1"})) or {}
    return _first(_request("POST", "/rest/v1/agp_aprendizados_longitudinais", payload={
        "pessoa_id": participant["pessoa_id"], "participante_id": participant["id"], "projeto_id": participant["projeto_id"],
        "ciclo_id": response.get("ciclo_id"), "decisao_id": intervention.get("decisao_id"), "intervencao_id": response["intervencao_id"],
        "resposta_intervencao_id": str(resposta_id), "tipo": payload.tipo, "descricao": payload.descricao,
        "evidencias": payload.evidencias, "confianca": payload.confianca, "interpretado_por": "profissional", "validado_por_pessoa_id": actor["pessoa_id"] if payload.status == "validado" else None,
        "status": payload.status,
    })) or {}
