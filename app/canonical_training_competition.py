from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant

router = APIRouter(prefix="/api/v1", tags=["canonical-training-competition"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _contexts(actor_pessoa_id: str, project_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
        "pessoa_id": f"eq.{actor_pessoa_id}", "projeto_id": f"eq.{project_id}", "status": "eq.ativo",
        "select": "papel_codigo,capacidades,competencias",
    }))


def _capabilities(contexts: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("codigo")
        for row in contexts
        for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }


def _authorize(actor_pessoa_id: str, participant: dict[str, Any], required: set[str], own_read: bool = False) -> dict[str, Any]:
    if own_read and actor_pessoa_id == str(participant["pessoa_id"]):
        return {"modo": "proprio", "papel_codigo": "athlete", "capacidades": ["own.read"]}
    project_id = str(participant.get("projeto_id") or "")
    contexts = _contexts(actor_pessoa_id, project_id)
    caps = _capabilities(contexts)
    if "platform.govern" in caps:
        return {"modo": "governanca", "papel_codigo": "master_governance", "capacidades": sorted(caps)}
    granted = sorted(caps.intersection(required))
    if not granted:
        raise HTTPException(status_code=403, detail="Papel atual não possui capacidade para esta operação")
    return {"modo": "profissional_projeto", "papel_codigo": contexts[0].get("papel_codigo") if contexts else None, "capacidades": granted}


class TrainingSessionCreate(BaseModel):
    data_hora_inicio: datetime
    duracao_min: int | None = Field(default=None, ge=1, le=600)
    volume_planejado: float | None = Field(default=None, ge=0)
    volume_executado: float | None = Field(default=None, ge=0)
    intensidade_planejada: float | None = Field(default=None, ge=0, le=10)
    intensidade_percebida: float | None = Field(default=None, ge=0, le=10)
    carga_externa: float | None = Field(default=None, ge=0)
    conteudo: dict[str, Any] = Field(default_factory=dict)
    intercorrencias: str | None = Field(default=None, max_length=2000)
    ciclo_id: UUID | None = None
    perfil_especializacao_id: UUID | None = None
    origem_registro: str = Field(default="manual", min_length=2, max_length=80)


class CompetitionParticipationCreate(BaseModel):
    competicao_id: UUID
    prova_id: UUID
    ciclo_id: UUID | None = None
    status: Literal["planejada", "inscrita", "confirmada", "disputada", "dns", "dnf", "dsq", "cancelada"] = "planejada"
    raia: str | None = Field(default=None, max_length=40)
    tempo_inscricao_ms: int | None = Field(default=None, ge=0)
    resultado_contexto: dict[str, Any] = Field(default_factory=dict)


class CompetitionResultUpdate(BaseModel):
    status: Literal["disputada", "dns", "dnf", "dsq", "cancelada"]
    tempo_oficial_ms: int | None = Field(default=None, ge=0)
    colocacao_serie: int | None = Field(default=None, ge=1)
    colocacao_geral: int | None = Field(default=None, ge=1)
    pontos: float | None = None
    fonte_resultado: str | None = Field(default=None, max_length=240)
    resultado_contexto: dict[str, Any] = Field(default_factory=dict)


class SplitCreate(BaseModel):
    distancia_acumulada_m: float = Field(gt=0)
    tempo_acumulado_ms: int = Field(ge=0)
    tempo_parcial_ms: int | None = Field(default=None, ge=0)
    origem: str = Field(default="oficial", min_length=2, max_length=80)
    qualidade: Literal["nao_avaliada", "confirmada", "estimada", "revisao_requerida"] = "nao_avaliada"
    contexto: dict[str, Any] = Field(default_factory=dict)


@router.get("/participantes/{participante_id}/treino-competicao")
def get_training_competition(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    access = _authorize(str(actor["pessoa_id"]), participant, {"training.plan", "training.record", "competition.record", "analysis.performance"}, own_read=True)
    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_treinamento_canonicas", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "data_hora_inicio.desc", "limit": "100"
    }))
    participations = _rows(_request("GET", "/rest/v1/agp_participacoes_competicao", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "created_at.desc", "limit": "100"
    }))
    ids = [str(x.get("id")) for x in participations if x.get("id")]
    splits = []
    if ids:
        splits = _rows(_request("GET", "/rest/v1/agp_parciais_competicao", params={
            "participacao_id": f"in.({','.join(ids)})", "select": "*", "order": "distancia_acumulada_m.asc"
        }))
    return {
        "modelo": "AGP-Training-Competition-v1",
        "participante_id": str(participante_id),
        "acesso": access,
        "sessoes": sessions,
        "participacoes_competicao": participations,
        "parciais_competicao": splits,
        "principio": "fato_operacional_antes_de_interpretacao",
    }


@router.post("/participantes/{participante_id}/sessoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_training_session(participante_id: UUID, payload: TrainingSessionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    _authorize(str(actor["pessoa_id"]), participant, {"training.record", "training.plan"})
    internal_load = None
    if payload.duracao_min is not None and payload.intensidade_percebida is not None:
        internal_load = round(payload.duracao_min * payload.intensidade_percebida, 2)
    created = _first(_request("POST", "/rest/v1/agp_sessoes_treinamento", payload={
        "pessoa_id": participant["pessoa_id"], "participante_id": participant["id"], "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None,
        "perfil_especializacao_id": str(payload.perfil_especializacao_id) if payload.perfil_especializacao_id else None,
        "tecnico_auth_id": str(user["id"]), "data_hora_inicio": payload.data_hora_inicio.isoformat(),
        "duracao_min": payload.duracao_min, "volume_planejado": payload.volume_planejado, "volume_executado": payload.volume_executado,
        "intensidade_planejada": payload.intensidade_planejada, "intensidade_percebida": payload.intensidade_percebida,
        "carga_interna": internal_load, "carga_externa": payload.carga_externa, "conteudo": payload.conteudo,
        "intercorrencias": payload.intercorrencias, "origem_registro": payload.origem_registro,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar sessão canônica")
    return created


@router.post("/participantes/{participante_id}/participacoes-competicao", status_code=status.HTTP_201_CREATED)
def create_competition_participation(participante_id: UUID, payload: CompetitionParticipationCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    _authorize(str(actor["pessoa_id"]), participant, {"competition.record", "decision.technical"})
    event = _first(_request("GET", "/rest/v1/agp_provas_competicao", params={"id": f"eq.{payload.prova_id}", "competicao_id": f"eq.{payload.competicao_id}", "select": "id,competicao_id", "limit": "1"}))
    if not event:
        raise HTTPException(status_code=422, detail="Prova não pertence à competição informada")
    created = _first(_request("POST", "/rest/v1/agp_participacoes_competicao", payload={
        "pessoa_id": participant["pessoa_id"], "participante_id": participant["id"], "projeto_id": participant["projeto_id"],
        "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None, "competicao_id": str(payload.competicao_id), "prova_id": str(payload.prova_id),
        "status": payload.status, "raia": payload.raia, "tempo_inscricao_ms": payload.tempo_inscricao_ms, "resultado_contexto": payload.resultado_contexto,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar participação competitiva")
    return created


@router.patch("/participacoes-competicao/{participacao_id}/resultado")
def update_competition_result(participacao_id: UUID, payload: CompetitionResultUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participation = _first(_request("GET", "/rest/v1/agp_participacoes_competicao", params={"id": f"eq.{participacao_id}", "select": "*", "limit": "1"}))
    if not participation:
        raise HTTPException(status_code=404, detail="Participação competitiva não encontrada")
    participant = _target_participant(UUID(str(participation["participante_id"])))
    _authorize(str(actor["pessoa_id"]), participant, {"competition.record", "evidence.review_technical"})
    updated = _first(_request("PATCH", "/rest/v1/agp_participacoes_competicao", params={"id": f"eq.{participacao_id}"}, payload={
        "status": payload.status, "tempo_oficial_ms": payload.tempo_oficial_ms, "colocacao_serie": payload.colocacao_serie,
        "colocacao_geral": payload.colocacao_geral, "pontos": payload.pontos, "fonte_resultado": payload.fonte_resultado,
        "resultado_contexto": payload.resultado_contexto, "confirmado_por_pessoa_id": actor["pessoa_id"],
        "confirmado_em": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat(),
    }))
    if not updated:
        raise HTTPException(status_code=502, detail="Falha ao atualizar resultado")
    return updated


@router.post("/participacoes-competicao/{participacao_id}/parciais", status_code=status.HTTP_201_CREATED)
def create_split(participacao_id: UUID, payload: SplitCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participation = _first(_request("GET", "/rest/v1/agp_participacoes_competicao", params={"id": f"eq.{participacao_id}", "select": "*", "limit": "1"}))
    if not participation:
        raise HTTPException(status_code=404, detail="Participação competitiva não encontrada")
    participant = _target_participant(UUID(str(participation["participante_id"])))
    _authorize(str(actor["pessoa_id"]), participant, {"competition.record", "analysis.performance"})
    created = _first(_request("POST", "/rest/v1/agp_parciais_competicao", payload={
        "participacao_id": str(participacao_id), "distancia_acumulada_m": payload.distancia_acumulada_m,
        "tempo_acumulado_ms": payload.tempo_acumulado_ms, "tempo_parcial_ms": payload.tempo_parcial_ms,
        "origem": payload.origem, "qualidade": payload.qualidade, "contexto": payload.contexto,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar parcial")
    return created
