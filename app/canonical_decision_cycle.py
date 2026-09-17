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

REGULATED_DOMAINS = {
    "medico": "medicine.clinical",
    "psicologico": "psychology.sport",
    "nutricional": "nutrition.sport",
    "fisiologico": "physiology.exercise",
    "fisiologia": "physiology.exercise",
    "fisioterapia": "physiotherapy.msk_rehab",
}

DOMAIN_COMPETENCES = {
    "tecnico": {"swimming.coaching", "swimming.technical_analysis", "performance.analysis"},
    "treino": {"swimming.training_design", "swimming.coaching", "strength_conditioning"},
    "recuperacao": {"strength_conditioning", "physiotherapy.msk_rehab", "physiology.exercise"},
    "competicao": {"swimming.coaching", "swimming.technical_analysis", "performance.analysis"},
    "contextual": {"performance.analysis", "swimming.coaching"},
    "fisico": {"strength_conditioning", "physiotherapy.msk_rehab"},
}


def _rows(v: Any) -> list[dict[str, Any]]:
    return v if isinstance(v, list) else []


def _first(v: Any) -> dict[str, Any] | None:
    rows = _rows(v)
    return rows[0] if rows else None


def _contexts(pessoa_id: str, projeto_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "projeto_id": f"eq.{projeto_id}",
        "status": "eq.ativo",
        "select": "papel_codigo,capacidades,competencias",
    }))


def _scope(actor_pessoa_id: str, participant: dict[str, Any], domain: str) -> dict[str, Any]:
    contexts = _contexts(actor_pessoa_id, str(participant.get("projeto_id") or ""))
    if not contexts:
        raise HTTPException(status_code=403, detail="Sem vínculo operacional ativo com o projeto")

    required_regulated = REGULATED_DOMAINS.get(domain)
    expected_competences = DOMAIN_COMPETENCES.get(domain, set())
    allowed_caps = {"decision.technical", "training.plan", "analysis.performance", "evidence.review_technical"}

    for context in contexts:
        caps = {
            item.get("codigo") for item in (context.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
        # Governança da plataforma não é autorização para operar o atleta.
        if "platform.govern" in caps and not caps.intersection(allowed_caps):
            continue

        competences = [
            item for item in (context.get("competencias") or [])
            if isinstance(item, dict) and item.get("codigo")
        ]

        if required_regulated:
            for competence in competences:
                if competence.get("codigo") != required_regulated:
                    continue
                if competence.get("requer_credencial_regulada") and not competence.get("credencial_verificada"):
                    continue
                return {
                    "papel_codigo": context.get("papel_codigo"),
                    "competencia_codigo": required_regulated,
                    "credencial_verificada": bool(competence.get("credencial_verificada")),
                    "requer_credencial": bool(competence.get("requer_credencial_regulada")),
                }
            continue

        if not caps.intersection(allowed_caps):
            continue
        selected = next(
            (item for item in competences if not expected_competences or item.get("codigo") in expected_competences),
            None,
        )
        return {
            "papel_codigo": context.get("papel_codigo"),
            "competencia_codigo": selected.get("codigo") if selected else None,
            "credencial_verificada": bool(selected.get("credencial_verificada")) if selected else False,
            "requer_credencial": bool(selected.get("requer_credencial_regulada")) if selected else False,
        }

    raise HTTPException(status_code=403, detail="Competência/capacidade insuficiente para atuar neste domínio")


class EvidenceRef(BaseModel):
    tipo_evidencia: Literal[
        "coleta", "metrica_observada", "serie_longitudinal", "sessao", "competicao",
        "avaliacao_profissional", "resultado_analitico", "marco", "intervencao_anterior",
        "resposta_anterior", "fonte_cientifica", "contexto"
    ]
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
    evidencias: list[EvidenceRef] = Field(min_items=1)


class InterventionCreate(BaseModel):
    descricao: str = Field(min_length=5, max_length=5000)
    resultado_esperado: dict[str, Any] = Field(default_factory=dict)
    fim_previsto: datetime | None = None
    status: Literal["proposta", "aprovada", "em_execucao"] = "proposta"


class ResponseCreate(BaseModel):
    conclusao: str = Field(min_length=5, max_length=5000)
    classificacao_profissional: Literal["favoravel", "neutra", "desfavoravel", "inconclusiva"] | None = None
    confianca: float | None = Field(default=None, ge=0, le=100)


class LearningCreate(BaseModel):
    tipo: Literal["fato", "padrao_observado", "hipotese", "limitacao", "resposta_a_intervencao", "nao_comparavel"]
    descricao: str = Field(min_length=5, max_length=5000)
    confianca: float | None = Field(default=None, ge=0, le=1)


def _comparability_snapshot(pessoa_id: str, domain: str) -> dict[str, Any]:
    series = _rows(_request("GET", "/rest/v1/agp_series_longitudinais_metricas", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "dominio": f"eq.{domain}",
        "select": "metrica_codigo,estado_comparabilidade,amostras,completude_media,confiabilidade_media",
    }))
    comparable = [item for item in series if item.get("estado_comparabilidade") == "comparavel"]
    review = [item for item in series if item.get("estado_comparabilidade") in {"nao_comparavel", "revisao_requerida"}]
    if comparable:
        state = "comparavel"
    elif review:
        state = "revisao_requerida"
    else:
        state = "dados_insuficientes"
    return {
        "estado": state,
        "series_total": len(series),
        "series_comparaveis": len(comparable),
        "series_revisao": len(review),
        "metricas": [item.get("metrica_codigo") for item in comparable],
    }


@router.get("/participantes/{participante_id}/ciclo-decisao-canonico")
def get_cycle(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]) and not _contexts(str(actor["pessoa_id"]), str(participant.get("projeto_id") or "")):
        raise HTTPException(status_code=403, detail="Sem vínculo ativo com o projeto do atleta")
    cycles = _rows(_request("GET", "/rest/v1/agp_ciclo_decisao_canonico", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "decisao_em.desc"
    }))
    return {
        "modelo": "AGP-Decision-Intervention-Response-Learning-v2",
        "participante_id": str(participante_id),
        "ciclos": cycles,
        "legado_score_global_necessario": False,
        "principio": "conteudo_humano_essencial_contexto_derivado_pelo_agp",
    }


@router.post("/participantes/{participante_id}/decisoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_decision(participante_id: UUID, payload: DecisionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _scope(str(actor["pessoa_id"]), participant, payload.dominio)
    for ev in payload.evidencias:
        if not ev.referencia_id and not ev.referencia_codigo:
            raise HTTPException(status_code=422, detail="Cada evidência precisa de referência")

    regulated = payload.dominio in REGULATED_DOMAINS
    decision = _first(_request("POST", "/rest/v1/agp_decisoes_canonicas", payload={
        "pessoa_id": participant["pessoa_id"],
        "participante_id": str(participante_id),
        "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None,
        "dominio": payload.dominio,
        "tipo": payload.tipo,
        "decisao": payload.decisao,
        "justificativa": payload.justificativa,
        "decidido_por_pessoa_id": actor["pessoa_id"],
        "papel_codigo": scope.get("papel_codigo"),
        "competencia_codigo": scope.get("competencia_codigo"),
        "exige_validacao_profissional": regulated,
        "dominio_validacao": payload.dominio if regulated else None,
    }))
    if not decision:
        raise HTTPException(status_code=502, detail="Falha ao registrar decisão")

    for ev in payload.evidencias:
        _request("POST", "/rest/v1/agp_decisao_evidencias", payload={
            "decisao_id": decision["id"],
            "tipo_evidencia": ev.tipo_evidencia,
            "referencia_id": str(ev.referencia_id) if ev.referencia_id else None,
            "referencia_codigo": ev.referencia_codigo,
            "papel": ev.papel,
            "resumo": ev.resumo,
        })
    return {
        "decisao": decision,
        "contexto_derivado": {
            "participante_id": str(participante_id),
            "projeto_id": participant["projeto_id"],
            "escopo_profissional": scope,
            "validacao_regulada": regulated,
        },
    }


@router.post("/decisoes-canonicas/{decisao_id}/intervencoes", status_code=status.HTTP_201_CREATED)
def create_intervention(decisao_id: UUID, payload: InterventionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    decision = _first(_request("GET", "/rest/v1/agp_decisoes_canonicas", params={
        "id": f"eq.{decisao_id}", "select": "*", "limit": "1"
    }))
    if not decision or not decision.get("participante_id"):
        raise HTTPException(status_code=404, detail="Decisão canônica não encontrada")

    participant = _target_participant(UUID(str(decision["participante_id"])))
    domain = str(decision.get("dominio") or "tecnico")
    scope = _scope(str(actor["pessoa_id"]), participant, domain)
    intervention = _first(_request("POST", "/rest/v1/agp_intervencoes", payload={
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "ciclo_id": decision.get("ciclo_id"),
        "decisao_id": str(decisao_id),
        "dominio": domain,
        "responsavel_auth_id": str(user["id"]),
        "papel_responsavel": scope.get("papel_codigo") or "canonical_role",
        "descricao": payload.descricao,
        "justificativa": decision.get("justificativa") or "Intervenção decorrente de decisão canônica rastreável.",
        "evidencia_origem": [{"decisao_id": str(decisao_id)}],
        "resultado_esperado": payload.resultado_esperado,
        "inicio": datetime.now(timezone.utc).isoformat(),
        "fim_previsto": payload.fim_previsto.isoformat() if payload.fim_previsto else None,
        "status": payload.status,
    }))
    if not intervention:
        raise HTTPException(status_code=502, detail="Falha ao registrar intervenção")
    _request("POST", "/rest/v1/agp_decisao_intervencoes", payload={
        "decisao_id": str(decisao_id), "intervencao_id": intervention["id"], "papel": "execucao"
    })
    return {
        "intervencao": intervention,
        "derivado_da_decisao": {"dominio": domain, "ciclo_id": decision.get("ciclo_id"), "justificativa": decision.get("justificativa")},
    }


@router.post("/intervencoes/{intervencao_id}/respostas-canonicas", status_code=status.HTTP_201_CREATED)
def create_response(intervencao_id: UUID, payload: ResponseCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    intervention = _first(_request("GET", "/rest/v1/agp_intervencoes_canonicas", params={
        "id": f"eq.{intervencao_id}", "select": "*", "limit": "1"
    }))
    if not intervention or not intervention.get("participante_id"):
        raise HTTPException(status_code=404, detail="Intervenção canônica não encontrada")

    participant = _target_participant(UUID(str(intervention["participante_id"])))
    domain = str(intervention.get("dominio") or "tecnico")
    scope = _scope(str(actor["pessoa_id"]), participant, domain)
    comparison = _comparability_snapshot(str(participant["pessoa_id"]), domain)
    legacy = {
        "favoravel": "melhora",
        "neutra": "neutra",
        "desfavoravel": "piora",
        "inconclusiva": "inconclusiva",
    }.get(payload.classificacao_profissional or "inconclusiva", "inconclusiva")

    response = _first(_request("POST", "/rest/v1/agp_respostas_intervencao", payload={
        "intervencao_id": str(intervencao_id),
        "participante_id": participant["id"],
        "pessoa_id": participant["pessoa_id"],
        "projeto_id": participant["projeto_id"],
        "avaliado_por_auth_id": str(user["id"]),
        "papel_avaliador": scope.get("papel_codigo") or "canonical_role",
        "data_avaliacao": datetime.now(timezone.utc).isoformat(),
        "metricas_antes": {},
        "metricas_depois": {},
        "variacoes": {"comparabilidade_derivada": comparison},
        "classificacao_resposta": legacy,
        "classificacao_profissional": payload.classificacao_profissional,
        "estado_comparabilidade": comparison["estado"],
        "significado_automatico": "mudanca_observada_sem_julgamento_sem_inferencia_causal",
        "confianca": payload.confianca,
        "conclusao": payload.conclusao,
        "ciclo_id": intervention.get("ciclo_id"),
        "visivel_atleta": True,
        "visivel_comissao": True,
        "visivel_instituicao": False,
    }))
    if not response:
        raise HTTPException(status_code=502, detail="Falha ao registrar resposta")
    return {
        "resposta": response,
        "comparabilidade_derivada": comparison,
        "principio": "profissional_registra_conclusao_agp_resolve_contexto_e_comparabilidade",
    }


@router.post("/respostas-intervencao/{resposta_id}/aprendizados", status_code=status.HTTP_201_CREATED)
def create_learning(resposta_id: UUID, payload: LearningCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    response = _first(_request("GET", "/rest/v1/agp_respostas_intervencao", params={
        "id": f"eq.{resposta_id}", "select": "*", "limit": "1"
    }))
    if not response:
        raise HTTPException(status_code=404, detail="Resposta não encontrada")

    participant = _target_participant(UUID(str(response["participante_id"])))
    intervention = _first(_request("GET", "/rest/v1/agp_intervencoes_canonicas", params={
        "id": f"eq.{response['intervencao_id']}", "select": "*", "limit": "1"
    })) or {}
    domain = str(intervention.get("dominio") or "tecnico")
    _scope(str(actor["pessoa_id"]), participant, domain)

    evidence = [{
        "resposta_intervencao_id": str(resposta_id),
        "intervencao_id": response.get("intervencao_id"),
        "decisao_id": intervention.get("decisao_id"),
        "estado_comparabilidade": response.get("estado_comparabilidade"),
        "classificacao_profissional": response.get("classificacao_profissional"),
    }]
    learning = _first(_request("POST", "/rest/v1/agp_aprendizados_longitudinais", payload={
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "ciclo_id": response.get("ciclo_id"),
        "decisao_id": intervention.get("decisao_id"),
        "intervencao_id": response["intervencao_id"],
        "resposta_intervencao_id": str(resposta_id),
        "tipo": payload.tipo,
        "descricao": payload.descricao,
        "evidencias": evidence,
        "confianca": payload.confianca,
        "interpretado_por": "profissional",
        "validado_por_pessoa_id": None,
        "status": "registrado",
    }))
    if not learning:
        raise HTTPException(status_code=502, detail="Falha ao registrar aprendizado")
    return {
        "aprendizado": learning,
        "evidencia_derivada": evidence,
        "principio": "aprendizado_rastreavel_sem_reentrada_manual_de_contexto",
    }
