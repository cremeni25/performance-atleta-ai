from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1/master", tags=["master-training-observability"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


@router.get("/treinos")
def master_training_overview(
    projeto_id: UUID | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_owner(authorization)

    project_params = {
        "select": "id,instituicao_id,nome,status",
        "order": "created_at.desc",
    }
    if projeto_id:
        project_params["id"] = f"eq.{projeto_id}"
    projects = _rows(_request("GET", "/rest/v1/agp_projetos_validacao", params=project_params))
    project_ids = [str(p["id"]) for p in projects if p.get("id")]

    plans = _rows(_request("GET", "/rest/v1/agp_planos_treino", params={
        "projeto_id": f"in.({','.join(project_ids)})",
        "select": "*",
        "order": "inicio_planejado.desc",
        "limit": "100",
    })) if project_ids else []

    plan_ids = [str(p["id"]) for p in plans if p.get("id")]
    recipients = _rows(_request("GET", "/rest/v1/agp_plano_treino_atletas", params={
        "plano_id": f"in.({','.join(plan_ids)})",
        "select": "*",
    })) if plan_ids else []

    participant_ids = sorted({str(r["participante_id"]) for r in recipients if r.get("participante_id")})
    participants = _rows(_request("GET", "/rest/v1/agp_participantes_elegibilidade", params={
        "participante_id": f"in.({','.join(participant_ids)})",
        "select": "participante_id,pessoa_id,projeto_id,nome,categoria,nivel,status_federativo",
    })) if participant_ids else []

    session_ids = [str(r["sessao_id"]) for r in recipients if r.get("sessao_id")]
    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "id": f"in.({','.join(session_ids)})",
        "select": "id,participante_id,status,objetivo,inicio_planejado,fim_planejado,inicio_real,fim_real,contexto_esportivo,planejado_por_pessoa_id,registrado_por_pessoa_id",
        "order": "inicio_planejado.desc",
    })) if session_ids else []

    units = _rows(_request("GET", "/rest/v1/agp_unidades_sessao", params={
        "sessao_id": f"in.({','.join(session_ids)})",
        "select": "id,sessao_id,parent_id,nivel,ordem,nome,objetivo,planejado,executado,status",
        "order": "sessao_id.asc,ordem.asc",
    })) if session_ids else []

    creator_ids = sorted({
        str(p["criado_por_pessoa_id"])
        for p in plans
        if p.get("criado_por_pessoa_id")
    })
    creators = _rows(_request("GET", "/rest/v1/agp_pessoas", params={
        "id": f"in.({','.join(creator_ids)})",
        "select": "id,nome",
    })) if creator_ids else []

    return {
        "modelo": "AGP-Master-Training-Observability-v1",
        "modo": "somente_leitura",
        "projetos": projects,
        "planos": plans,
        "destinos": recipients,
        "participantes": participants,
        "sessoes": sessions,
        "unidades": units,
        "criadores": creators,
        "principio": "governanca_observa_sem_operar",
    }
