from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant
from app.canonical_training_competition import _contexts, _resolve_profile, _resolve_cycle

router = APIRouter(prefix="/api/v1", tags=["canonical-training-planning"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _project_scope(actor_pessoa_id: str, project_id: str, required: set[str]) -> dict[str, Any]:
    contexts = _contexts(actor_pessoa_id, project_id)
    for context in contexts:
        caps = {
            item.get("codigo")
            for item in (context.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
        granted = sorted(caps.intersection(required))
        if granted:
            return {
                "papel_codigo": context.get("papel_codigo"),
                "capacidades": granted,
            }
    raise HTTPException(status_code=403, detail="Sem capacidade profissional para planejar/registrar treino neste projeto")


def _participant_in_project(participant_id: UUID, project_id: str) -> dict[str, Any]:
    participant = _target_participant(participant_id)
    if str(participant.get("projeto_id") or "") != str(project_id):
        raise HTTPException(status_code=422, detail="Atleta não pertence ao projeto do treino")
    if str(participant.get("funcao_no_projeto") or "atleta") != "atleta":
        raise HTTPException(status_code=422, detail="Destino do treino precisa ser atleta")
    return participant


class GroupCreate(BaseModel):
    projeto_id: UUID
    nome: str = Field(min_length=2, max_length=160)
    descricao: str | None = Field(default=None, max_length=1000)
    participante_ids: list[UUID] = Field(default_factory=list)


class GroupMembersUpdate(BaseModel):
    participante_ids: list[UUID]


class AthleteAdjustment(BaseModel):
    participante_id: UUID
    observacao: str | None = Field(default=None, max_length=2000)
    volume_planejado: float | None = Field(default=None, ge=0)
    intensidade_planejada: float | None = Field(default=None, ge=0, le=10)
    conteudo: str | None = Field(default=None, max_length=8000)


class TrainingPlanCreate(BaseModel):
    projeto_id: UUID
    grupo_id: UUID | None = None
    participante_ids: list[UUID] = Field(default_factory=list)
    tipo_sessao: Literal["pool_training", "dry_land", "recovery", "assessment", "other"] = "pool_training"
    inicio_planejado: datetime
    duracao_min: int | None = Field(default=None, ge=1, le=600)
    objetivo: str | None = Field(default=None, max_length=2000)
    volume_planejado: float | None = Field(default=None, ge=0)
    intensidade_planejada: float | None = Field(default=None, ge=0, le=10)
    conteudo: str = Field(min_length=2, max_length=12000)
    ciclo_id: UUID | None = None
    ajustes_individuais: list[AthleteAdjustment] = Field(default_factory=list)


class SessionExecutionUpdate(BaseModel):
    status: Literal["em_execucao", "concluida", "cancelada"]
    inicio_real: datetime | None = None
    fim_real: datetime | None = None
    volume_executado: float | None = Field(default=None, ge=0)
    intensidade_percebida: float | None = Field(default=None, ge=0, le=10)
    conteudo_executado: str | None = Field(default=None, max_length=12000)
    intercorrencias: str | None = Field(default=None, max_length=3000)


@router.get("/projetos/{projeto_id}/planejamento-treinos")
def get_training_planning(projeto_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(projeto_id), {"training.plan", "training.record"})

    groups = _rows(_request("GET", "/rest/v1/agp_grupos_treinamento", params={
        "projeto_id": f"eq.{projeto_id}",
        "ativo": "eq.true",
        "select": "*",
        "order": "nome.asc",
    }))
    memberships = _rows(_request("GET", "/rest/v1/agp_grupo_treinamento_participantes", params={
        "grupo_id": f"in.({','.join(str(item['id']) for item in groups)})" if groups else "eq.00000000-0000-0000-0000-000000000000",
        "ativo": "eq.true",
        "select": "*",
    })) if groups else []

    athletes = _rows(_request("GET", "/rest/v1/agp_participantes_elegibilidade", params={
        "projeto_id": f"eq.{projeto_id}",
        "funcao_no_projeto": "eq.atleta",
        "ativo": "eq.true",
        "select": "participante_id,pessoa_id,nome,status_calculado,status_registrado,tecnico_responsavel_pessoa_id,modalidade,prova_posicao,categoria,nivel,status_federativo,federacao_nome,registro_federativo",
        "order": "nome.asc",
    }))

    plans = _rows(_request("GET", "/rest/v1/agp_planos_treino", params={
        "projeto_id": f"eq.{projeto_id}",
        "select": "*",
        "order": "inicio_planejado.desc",
        "limit": "50",
    }))
    plan_ids = [str(item["id"]) for item in plans if item.get("id")]
    recipients = _rows(_request("GET", "/rest/v1/agp_plano_treino_atletas", params={
        "plano_id": f"in.({','.join(plan_ids)})",
        "select": "*",
    })) if plan_ids else []
    session_ids = [str(item["sessao_id"]) for item in recipients if item.get("sessao_id")]
    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "id": f"in.({','.join(session_ids)})",
        "select": "id,participante_id,tipo_sessao,status,objetivo,inicio_planejado,fim_planejado,inicio_real,fim_real,contexto_esportivo",
        "order": "inicio_planejado.desc",
    })) if session_ids else []

    return {
        "modelo": "AGP-Swimming-Training-Planning-v1",
        "projeto_id": str(projeto_id),
        "escopo_profissional": scope,
        "grupos": groups,
        "membros_grupos": memberships,
        "atletas": athletes,
        "planos": plans,
        "destinos_planos": recipients,
        "sessoes_materializadas": sessions,
        "principio": "prescricao_coletiva_com_individualizacao_sem_perder_o_atleta_como_centro_longitudinal",
    }


@router.post("/projetos/{projeto_id}/grupos-treinamento", status_code=status.HTTP_201_CREATED)
def create_group(projeto_id: UUID, payload: GroupCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if str(payload.projeto_id) != str(projeto_id):
        raise HTTPException(status_code=422, detail="Projeto divergente")
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(projeto_id), {"training.plan"})

    for participant_id in payload.participante_ids:
        _participant_in_project(participant_id, str(projeto_id))

    # Resolve sport profile from one athlete when possible, otherwise project context.
    profile_id: str | None = None
    if payload.participante_ids:
        participant = _participant_in_project(payload.participante_ids[0], str(projeto_id))
        profile_id, _ = _resolve_profile(participant)
    else:
        ctx = _first(_request("GET", "/rest/v1/agp_contextos_globais_projeto", params={
            "projeto_id": f"eq.{projeto_id}",
            "select": "perfil_especializacao_id",
            "limit": "1",
        }))
        profile_id = str(ctx["perfil_especializacao_id"]) if ctx and ctx.get("perfil_especializacao_id") else None
    if not profile_id:
        raise HTTPException(status_code=422, detail="Perfil esportivo do projeto não pôde ser resolvido")

    group = _first(_request("POST", "/rest/v1/agp_grupos_treinamento", payload={
        "projeto_id": str(projeto_id),
        "perfil_especializacao_id": profile_id,
        "nome": payload.nome.strip(),
        "descricao": payload.descricao,
        "ativo": True,
        "criado_por_pessoa_id": actor["pessoa_id"],
    }))
    if not group:
        raise HTTPException(status_code=502, detail="Falha ao criar grupo de treinamento")

    for participant_id in payload.participante_ids:
        _request("POST", "/rest/v1/agp_grupo_treinamento_participantes", payload={
            "grupo_id": group["id"],
            "participante_id": str(participant_id),
            "ativo": True,
        })

    return {"grupo": group, "participante_ids": [str(x) for x in payload.participante_ids], "escopo_profissional": scope}


@router.put("/grupos-treinamento/{grupo_id}/participantes")
def replace_group_members(grupo_id: UUID, payload: GroupMembersUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    group = _first(_request("GET", "/rest/v1/agp_grupos_treinamento", params={
        "id": f"eq.{grupo_id}", "select": "*", "limit": "1"
    }))
    if not group:
        raise HTTPException(status_code=404, detail="Grupo de treinamento não encontrado")

    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(group["projeto_id"]), {"training.plan"})
    for participant_id in payload.participante_ids:
        _participant_in_project(participant_id, str(group["projeto_id"]))

    _request("DELETE", "/rest/v1/agp_grupo_treinamento_participantes", params={"grupo_id": f"eq.{grupo_id}"})
    for participant_id in payload.participante_ids:
        _request("POST", "/rest/v1/agp_grupo_treinamento_participantes", payload={
            "grupo_id": str(grupo_id),
            "participante_id": str(participant_id),
            "ativo": True,
        })
    return {"grupo_id": str(grupo_id), "participante_ids": [str(x) for x in payload.participante_ids], "escopo_profissional": scope}


@router.post("/projetos/{projeto_id}/planos-treino", status_code=status.HTTP_201_CREATED)
def create_training_plan(projeto_id: UUID, payload: TrainingPlanCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if str(payload.projeto_id) != str(projeto_id):
        raise HTTPException(status_code=422, detail="Projeto divergente")
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(projeto_id), {"training.plan", "training.record"})

    group_member_ids: list[UUID] = []
    if payload.grupo_id:
        group = _first(_request("GET", "/rest/v1/agp_grupos_treinamento", params={
            "id": f"eq.{payload.grupo_id}",
            "projeto_id": f"eq.{projeto_id}",
            "ativo": "eq.true",
            "select": "*",
            "limit": "1",
        }))
        if not group:
            raise HTTPException(status_code=422, detail="Grupo não pertence ao projeto")
        rows = _rows(_request("GET", "/rest/v1/agp_grupo_treinamento_participantes", params={
            "grupo_id": f"eq.{payload.grupo_id}",
            "ativo": "eq.true",
            "select": "participante_id",
        }))
        group_member_ids = [UUID(str(row["participante_id"])) for row in rows]

    targets: list[UUID] = []
    seen: set[str] = set()
    for item in [*group_member_ids, *payload.participante_ids]:
        key = str(item)
        if key not in seen:
            seen.add(key)
            targets.append(item)
    if not targets:
        raise HTTPException(status_code=422, detail="Selecione ao menos um grupo ou atleta")

    participants = [_participant_in_project(item, str(projeto_id)) for item in targets]
    profile_id, profile_source = _resolve_profile(participants[0], cycle=_resolve_cycle(participants[0], payload.ciclo_id) if payload.ciclo_id else None)
    adjustment_map = {str(item.participante_id): item for item in payload.ajustes_individuais}

    plan = _first(_request("POST", "/rest/v1/agp_planos_treino", payload={
        "projeto_id": str(projeto_id),
        "perfil_especializacao_id": profile_id,
        "grupo_id": str(payload.grupo_id) if payload.grupo_id else None,
        "tipo_sessao": payload.tipo_sessao,
        "status": "planejado",
        "objetivo": payload.objetivo,
        "inicio_planejado": payload.inicio_planejado.isoformat(),
        "duracao_min": payload.duracao_min,
        "prescricao_base": {
            "volume_planejado": payload.volume_planejado,
            "intensidade_planejada": payload.intensidade_planejada,
            "conteudo": payload.conteudo,
            "ciclo_id": str(payload.ciclo_id) if payload.ciclo_id else None,
        },
        "criado_por_pessoa_id": actor["pessoa_id"],
    }))
    if not plan:
        raise HTTPException(status_code=502, detail="Falha ao criar plano de treino")

    sessions: list[dict[str, Any]] = []
    end = payload.inicio_planejado + timedelta(minutes=payload.duracao_min) if payload.duracao_min else None

    for participant in participants:
        participant_id = str(participant["id"])
        adjustment = adjustment_map.get(participant_id)
        adjustment_payload = {
            "observacao": adjustment.observacao if adjustment else None,
            "volume_planejado": adjustment.volume_planejado if adjustment else None,
            "intensidade_planejada": adjustment.intensidade_planejada if adjustment else None,
            "conteudo": adjustment.conteudo if adjustment else None,
        }
        session_context = {
            "plano_treino_id": plan["id"],
            "origem_prescricao": "grupo" if str(participant["id"]) in {str(x) for x in group_member_ids} else "individual",
            "volume_planejado": adjustment.volume_planejado if adjustment and adjustment.volume_planejado is not None else payload.volume_planejado,
            "intensidade_planejada": adjustment.intensidade_planejada if adjustment and adjustment.intensidade_planejada is not None else payload.intensidade_planejada,
            "conteudo": adjustment.conteudo if adjustment and adjustment.conteudo else payload.conteudo,
            "ajuste_individual": adjustment_payload,
            "origem_registro": "planejamento_profissional_agp",
        }
        session = _first(_request("POST", "/rest/v1/agp_sessoes_esportivas", payload={
            "projeto_id": str(projeto_id),
            "participante_id": participant_id,
            "perfil_especializacao_id": profile_id,
            "tipo_sessao": payload.tipo_sessao,
            "status": "planejada",
            "objetivo": payload.objetivo,
            "inicio_planejado": payload.inicio_planejado.isoformat(),
            "fim_planejado": end.isoformat() if end else None,
            "contexto_esportivo": session_context,
            "planejado_por_pessoa_id": actor["pessoa_id"],
            "registrado_por_pessoa_id": actor["pessoa_id"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }))
        if not session:
            raise HTTPException(status_code=502, detail="Falha ao materializar sessão individual do plano")

        _request("POST", "/rest/v1/agp_plano_treino_atletas", payload={
            "plano_id": plan["id"],
            "participante_id": participant_id,
            "origem": "grupo" if str(participant["id"]) in {str(x) for x in group_member_ids} else "individual",
            "ajustes_individuais": adjustment_payload,
            "sessao_id": session["id"],
        })
        if payload.ciclo_id:
            _request("POST", "/rest/v1/agp_ciclo_sessoes", payload={
                "ciclo_id": str(payload.ciclo_id),
                "sessao_id": session["id"],
            })
        sessions.append(session)

    return {
        "plano": plan,
        "sessoes_criadas": sessions,
        "atletas_total": len(sessions),
        "perfil_especializacao": {"id": profile_id, "derivado_de": profile_source},
        "escopo_profissional": scope,
    }


@router.patch("/sessoes-canonicas/{sessao_id}/execucao")
def update_session_execution(sessao_id: UUID, payload: SessionExecutionUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    session = _first(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "id": f"eq.{sessao_id}", "select": "*", "limit": "1"
    }))
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    participant = _target_participant(UUID(str(session["participante_id"])))
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(session["projeto_id"]), {"training.record", "training.plan"})

    context = dict(session.get("contexto_esportivo") or {})
    if payload.volume_executado is not None:
        context["volume_executado"] = payload.volume_executado
    if payload.intensidade_percebida is not None:
        context["intensidade_percebida"] = payload.intensidade_percebida
    if payload.conteudo_executado is not None:
        context["conteudo_executado"] = payload.conteudo_executado
    if payload.intercorrencias is not None:
        context["intercorrencias"] = payload.intercorrencias

    start_real = payload.inicio_real or (datetime.now(timezone.utc) if payload.status == "em_execucao" and not session.get("inicio_real") else session.get("inicio_real"))
    end_real = payload.fim_real or (datetime.now(timezone.utc) if payload.status == "concluida" else session.get("fim_real"))

    updated = _first(_request("PATCH", "/rest/v1/agp_sessoes_esportivas", params={
        "id": f"eq.{sessao_id}"
    }, payload={
        "status": payload.status,
        "inicio_real": start_real.isoformat() if isinstance(start_real, datetime) else start_real,
        "fim_real": end_real.isoformat() if isinstance(end_real, datetime) else end_real,
        "contexto_esportivo": context,
        "registrado_por_pessoa_id": actor["pessoa_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))
    if not updated:
        raise HTTPException(status_code=502, detail="Falha ao registrar execução da sessão")

    return {
        "sessao": updated,
        "participante_id": str(participant["id"]),
        "escopo_profissional": scope,
        "principio": "execucao_real_preservada_por_atleta_mesmo_quando_a_prescricao_foi_coletiva",
    }
