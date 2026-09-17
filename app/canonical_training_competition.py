from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        "pessoa_id": f"eq.{actor_pessoa_id}",
        "projeto_id": f"eq.{project_id}",
        "status": "eq.ativo",
        "select": "papel_codigo,capacidades,competencias",
    }))


def _capabilities(contexts: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("codigo")
        for row in contexts
        for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }


def _authorize(
    actor_pessoa_id: str,
    participant: dict[str, Any],
    required: set[str],
    *,
    own_read: bool = False,
) -> dict[str, Any]:
    if own_read and actor_pessoa_id == str(participant["pessoa_id"]):
        return {"modo": "proprio", "papel_codigo": "athlete", "capacidades": ["own.read"]}

    project_id = str(participant.get("projeto_id") or "")
    contexts = _contexts(actor_pessoa_id, project_id)
    if not contexts:
        raise HTTPException(status_code=403, detail="Sem vínculo operacional ativo com o projeto do atleta")

    for context in contexts:
        caps = {
            item.get("codigo")
            for item in (context.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
        granted = sorted(caps.intersection(required))
        if granted:
            return {
                "modo": "profissional_projeto",
                "papel_codigo": context.get("papel_codigo"),
                "capacidades": granted,
            }

    # platform.govern é governança do sistema, não autorização esportiva.
    # O Master só opera se possuir, separadamente, um papel profissional válido no projeto.
    all_caps = _capabilities(contexts)
    if "platform.govern" in all_caps:
        raise HTTPException(
            status_code=403,
            detail="Governança da plataforma não autoriza operação de treino ou competição do atleta",
        )
    raise HTTPException(status_code=403, detail="Papel atual não possui capacidade para esta operação")


def _resolve_cycle(participant: dict[str, Any], ciclo_id: UUID | None) -> dict[str, Any] | None:
    if not ciclo_id:
        return None
    cycle = _first(_request("GET", "/rest/v1/agp_ciclos_longitudinais", params={
        "id": f"eq.{ciclo_id}",
        "pessoa_id": f"eq.{participant['pessoa_id']}",
        "select": "id,pessoa_id,participante_id,projeto_id,perfil_especializacao_id,nivel,status",
        "limit": "1",
    }))
    if not cycle:
        raise HTTPException(status_code=422, detail="Ciclo não pertence ao histórico longitudinal deste atleta")
    if cycle.get("projeto_id") and str(cycle["projeto_id"]) != str(participant.get("projeto_id")):
        raise HTTPException(status_code=422, detail="Ciclo pertence a outro projeto")
    return cycle


def _resolve_profile(
    participant: dict[str, Any],
    *,
    cycle: dict[str, Any] | None = None,
    competition_id: UUID | None = None,
) -> tuple[str, str]:
    if competition_id:
        competition = _first(_request("GET", "/rest/v1/agp_competicoes", params={
            "id": f"eq.{competition_id}",
            "select": "id,projeto_id,perfil_especializacao_id",
            "limit": "1",
        }))
        if not competition:
            raise HTTPException(status_code=422, detail="Competição não encontrada")
        if str(competition.get("projeto_id")) != str(participant.get("projeto_id")):
            raise HTTPException(status_code=422, detail="Competição pertence a outro projeto")
        if competition.get("perfil_especializacao_id"):
            return str(competition["perfil_especializacao_id"]), "competicao"

    if cycle and cycle.get("perfil_especializacao_id"):
        return str(cycle["perfil_especializacao_id"]), "ciclo_longitudinal"

    project_context = _first(_request("GET", "/rest/v1/agp_contextos_globais_projeto", params={
        "projeto_id": f"eq.{participant['projeto_id']}",
        "select": "perfil_especializacao_id",
        "limit": "1",
    }))
    if project_context and project_context.get("perfil_especializacao_id"):
        return str(project_context["perfil_especializacao_id"]), "contexto_global_projeto"

    profiles = _rows(_request("GET", "/rest/v1/agp_perfis_especializacao_esportiva", params={
        "select": "id,codigo,versao,status_catalogo",
        "limit": "2",
    }))
    if len(profiles) == 1:
        return str(profiles[0]["id"]), "perfil_unico_catalogo_p0"

    raise HTTPException(
        status_code=422,
        detail="Perfil esportivo não pôde ser derivado do ciclo, competição ou contexto do projeto",
    )


def _session_end(start: datetime, duration_min: int | None) -> datetime | None:
    if duration_min is None:
        return None
    return start + timedelta(minutes=duration_min)


class TrainingSessionCreate(BaseModel):
    data_hora_inicio: datetime
    tipo_sessao: Literal["pool_training", "dry_land", "recovery", "assessment", "other"] = "pool_training"
    status: Literal["planejada", "em_execucao", "concluida", "cancelada"] = "planejada"
    objetivo: str | None = Field(default=None, max_length=2000)
    duracao_min: int | None = Field(default=None, ge=1, le=600)
    volume_planejado: float | None = Field(default=None, ge=0)
    volume_executado: float | None = Field(default=None, ge=0)
    intensidade_planejada: float | None = Field(default=None, ge=0, le=10)
    intensidade_percebida: float | None = Field(default=None, ge=0, le=10)
    carga_externa: float | None = Field(default=None, ge=0)
    conteudo: dict[str, Any] = Field(default_factory=dict)
    intercorrencias: str | None = Field(default=None, max_length=2000)
    ciclo_id: UUID | None = None
    origem_registro: str = Field(default="manual", min_length=2, max_length=80)


class CompetitionParticipationCreate(BaseModel):
    competicao_id: UUID
    prova_id: UUID
    ciclo_id: UUID | None = None
    status: Literal["inscrito", "confirmado", "realizado", "dns", "dnf", "dsq", "cancelado"] = "inscrito"
    raia: int | None = Field(default=None, ge=0)
    tempo_inscricao_ms: int | None = Field(default=None, ge=0)
    resultado_contexto: dict[str, Any] = Field(default_factory=dict)


class CompetitionResultUpdate(BaseModel):
    status: Literal["realizado", "dns", "dnf", "dsq", "cancelado"]
    tempo_oficial_ms: int | None = Field(default=None, ge=0)
    classificacao: int | None = Field(default=None, ge=1)
    colocacao_serie: int | None = Field(default=None, ge=1)
    pontos: float | None = None
    codigo_desclassificacao: str | None = Field(default=None, max_length=120)
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
def get_training_competition(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    access = _authorize(
        str(actor["pessoa_id"]),
        participant,
        {"training.plan", "training.record", "competition.record", "analysis.performance"},
        own_read=True,
    )

    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "*",
        "order": "created_at.desc",
        "limit": "100",
    }))
    participations = _rows(_request("GET", "/rest/v1/agp_participacoes_prova", params={
        "participante_id": f"eq.{participante_id}",
        "select": "*",
        "order": "created_at.desc",
        "limit": "100",
    }))
    participation_ids = [str(item["id"]) for item in participations if item.get("id")]
    segments: list[dict[str, Any]] = []
    if participation_ids:
        segments = _rows(_request("GET", "/rest/v1/agp_segmentos_prova", params={
            "participacao_id": f"in.({','.join(participation_ids)})",
            "select": "*",
            "order": "participacao_id.asc,ordem.asc",
        }))

    session_ids = [str(item["id"]) for item in sessions if item.get("id")]
    session_cycles: list[dict[str, Any]] = []
    if session_ids:
        session_cycles = _rows(_request("GET", "/rest/v1/agp_ciclo_sessoes", params={
            "sessao_id": f"in.({','.join(session_ids)})",
            "select": "ciclo_id,sessao_id",
        }))
    participation_cycles: list[dict[str, Any]] = []
    if participation_ids:
        participation_cycles = _rows(_request("GET", "/rest/v1/agp_ciclo_participacoes_prova", params={
            "participacao_prova_id": f"in.({','.join(participation_ids)})",
            "select": "ciclo_id,participacao_prova_id",
        }))

    return {
        "modelo": "AGP-Training-Competition-v2",
        "fonte_verdade": {
            "treino": "agp_sessoes_esportivas",
            "competicao": "agp_participacoes_prova",
            "segmentos": "agp_segmentos_prova",
        },
        "participante_id": str(participante_id),
        "acesso": access,
        "sessoes": sessions,
        "vinculos_ciclo_sessoes": session_cycles,
        "participacoes_prova": participations,
        "vinculos_ciclo_participacoes": participation_cycles,
        "segmentos_prova": segments,
        "principio": "fato_operacional_antes_de_interpretacao_sem_score_global",
    }


@router.post("/participantes/{participante_id}/sessoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_training_session(
    participante_id: UUID,
    payload: TrainingSessionCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _authorize(str(actor["pessoa_id"]), participant, {"training.record", "training.plan"})
    cycle = _resolve_cycle(participant, payload.ciclo_id)
    profile_id, profile_source = _resolve_profile(participant, cycle=cycle)

    end = _session_end(payload.data_hora_inicio, payload.duracao_min)
    context = {
        "volume_planejado": payload.volume_planejado,
        "volume_executado": payload.volume_executado,
        "intensidade_planejada": payload.intensidade_planejada,
        "intensidade_percebida": payload.intensidade_percebida,
        "carga_externa": payload.carga_externa,
        "conteudo": payload.conteudo,
        "intercorrencias": payload.intercorrencias,
        "origem_registro": payload.origem_registro,
        "nota_carga_interna": "nao_calculada_sem_formula_protocolo_e_versao_cientifica_explicita",
    }
    created = _first(_request("POST", "/rest/v1/agp_sessoes_esportivas", payload={
        "projeto_id": participant["projeto_id"],
        "participante_id": participant["id"],
        "perfil_especializacao_id": profile_id,
        "tipo_sessao": payload.tipo_sessao,
        "status": payload.status,
        "objetivo": payload.objetivo,
        "inicio_planejado": payload.data_hora_inicio.isoformat(),
        "fim_planejado": end.isoformat() if end else None,
        "inicio_real": payload.data_hora_inicio.isoformat() if payload.status in {"em_execucao", "concluida"} else None,
        "fim_real": end.isoformat() if end and payload.status == "concluida" else None,
        "contexto_esportivo": context,
        "planejado_por_pessoa_id": actor["pessoa_id"],
        "registrado_por_pessoa_id": actor["pessoa_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar sessão esportiva canônica")

    if cycle:
        _request("POST", "/rest/v1/agp_ciclo_sessoes", payload={
            "ciclo_id": cycle["id"],
            "sessao_id": created["id"],
        })

    return {
        "sessao": created,
        "ciclo_id": cycle.get("id") if cycle else None,
        "perfil_especializacao": {"id": profile_id, "derivado_de": profile_source},
        "escopo_profissional": scope,
        "carga_interna_automatica": False,
    }


@router.post("/participantes/{participante_id}/participacoes-competicao", status_code=status.HTTP_201_CREATED)
def create_competition_participation(
    participante_id: UUID,
    payload: CompetitionParticipationCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _authorize(str(actor["pessoa_id"]), participant, {"competition.record", "decision.technical"})
    cycle = _resolve_cycle(participant, payload.ciclo_id)

    event = _first(_request("GET", "/rest/v1/agp_provas_competicao", params={
        "id": f"eq.{payload.prova_id}",
        "competicao_id": f"eq.{payload.competicao_id}",
        "select": "id,competicao_id",
        "limit": "1",
    }))
    if not event:
        raise HTTPException(status_code=422, detail="Prova não pertence à competição informada")
    profile_id, profile_source = _resolve_profile(
        participant,
        cycle=cycle,
        competition_id=payload.competicao_id,
    )

    result_context = dict(payload.resultado_contexto)
    if payload.tempo_inscricao_ms is not None:
        result_context["tempo_inscricao_ms"] = payload.tempo_inscricao_ms

    created = _first(_request("POST", "/rest/v1/agp_participacoes_prova", payload={
        "prova_id": str(payload.prova_id),
        "participante_id": participant["id"],
        "raia": payload.raia,
        "status": payload.status,
        "fonte_resultado": {},
        "contexto_resultado": result_context,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar participação competitiva canônica")

    if cycle:
        _request("POST", "/rest/v1/agp_ciclo_participacoes_prova", payload={
            "ciclo_id": cycle["id"],
            "participacao_prova_id": created["id"],
        })

    return {
        "participacao": created,
        "ciclo_id": cycle.get("id") if cycle else None,
        "perfil_especializacao": {"id": profile_id, "derivado_de": profile_source},
        "escopo_profissional": scope,
    }


@router.patch("/participacoes-competicao/{participacao_id}/resultado")
def update_competition_result(
    participacao_id: UUID,
    payload: CompetitionResultUpdate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participation = _first(_request("GET", "/rest/v1/agp_participacoes_prova", params={
        "id": f"eq.{participacao_id}",
        "select": "*",
        "limit": "1",
    }))
    if not participation:
        raise HTTPException(status_code=404, detail="Participação competitiva não encontrada")
    participant = _target_participant(UUID(str(participation["participante_id"])))
    scope = _authorize(
        str(actor["pessoa_id"]),
        participant,
        {"competition.record", "evidence.review_technical"},
    )

    context = dict(participation.get("contexto_resultado") or {})
    context.update(payload.resultado_contexto)
    if payload.colocacao_serie is not None:
        context["colocacao_serie"] = payload.colocacao_serie
    if payload.pontos is not None:
        context["pontos"] = payload.pontos
    context["confirmado_por_pessoa_id"] = str(actor["pessoa_id"])
    context["confirmado_em"] = datetime.now(timezone.utc).isoformat()

    source = dict(participation.get("fonte_resultado") or {})
    if payload.fonte_resultado:
        source["descricao"] = payload.fonte_resultado

    updated = _first(_request("PATCH", "/rest/v1/agp_participacoes_prova", params={
        "id": f"eq.{participacao_id}"
    }, payload={
        "status": payload.status,
        "tempo_oficial_ms": payload.tempo_oficial_ms,
        "classificacao": payload.classificacao,
        "codigo_desclassificacao": payload.codigo_desclassificacao,
        "fonte_resultado": source,
        "contexto_resultado": context,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))
    if not updated:
        raise HTTPException(status_code=502, detail="Falha ao atualizar resultado competitivo")
    return {"participacao": updated, "escopo_profissional": scope}


@router.post("/participacoes-competicao/{participacao_id}/parciais", status_code=status.HTTP_201_CREATED)
def create_split(
    participacao_id: UUID,
    payload: SplitCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participation = _first(_request("GET", "/rest/v1/agp_participacoes_prova", params={
        "id": f"eq.{participacao_id}",
        "select": "*",
        "limit": "1",
    }))
    if not participation:
        raise HTTPException(status_code=404, detail="Participação competitiva não encontrada")
    participant = _target_participant(UUID(str(participation["participante_id"])))
    scope = _authorize(str(actor["pessoa_id"]), participant, {"competition.record", "analysis.performance"})

    existing = _rows(_request("GET", "/rest/v1/agp_segmentos_prova", params={
        "participacao_id": f"eq.{participacao_id}",
        "select": "ordem,fim_m",
        "order": "ordem.desc",
        "limit": "1",
    }))
    previous = existing[0] if existing else None
    order = int(previous.get("ordem", -1)) + 1 if previous else 0
    start_m = previous.get("fim_m") if previous else 0
    if start_m is not None and float(payload.distancia_acumulada_m) <= float(start_m):
        raise HTTPException(status_code=422, detail="Distância acumulada precisa avançar em relação ao segmento anterior")

    data = dict(payload.contexto)
    data.update({
        "distancia_acumulada_m": payload.distancia_acumulada_m,
        "tempo_acumulado_ms": payload.tempo_acumulado_ms,
        "tempo_parcial_ms": payload.tempo_parcial_ms,
        "origem": payload.origem,
        "qualidade": payload.qualidade,
    })
    created = _first(_request("POST", "/rest/v1/agp_segmentos_prova", payload={
        "participacao_id": str(participacao_id),
        "ordem": order,
        "tipo_segmento": "split",
        "inicio_m": start_m,
        "fim_m": payload.distancia_acumulada_m,
        "tempo_ms": payload.tempo_parcial_ms if payload.tempo_parcial_ms is not None else payload.tempo_acumulado_ms,
        "dados_segmento": data,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar segmento/parcial canônico")
    return {"segmento": created, "escopo_profissional": scope}
