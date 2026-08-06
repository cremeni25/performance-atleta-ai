from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Header, HTTPException, status

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1", tags=["athlete-technician-management"])


def _person_name(person_id: str | None) -> str | None:
    if not person_id:
        return None
    rows = _request("GET", "/rest/v1/agp_pessoas", params={"id": f"eq.{person_id}", "select": "nome", "limit": "1"})
    return rows[0].get("nome") if isinstance(rows, list) and rows else None


@router.patch("/participantes/{participante_id}/vinculo-tecnico")
def change_athlete_technician(
    participante_id: UUID,
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    technician_id = str(payload.get("tecnico_responsavel_pessoa_id") or "").strip()
    reason = str(payload.get("motivo") or "Alteração operacional na ficha do atleta").strip()
    if not technician_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selecione o técnico responsável")

    rows = _request("GET", "/rest/v1/agp_participantes_projeto", params={
        "id": f"eq.{participante_id}",
        "select": "id,projeto_id,pessoa_id,funcao_no_projeto,tecnico_responsavel_pessoa_id,status_onboarding",
        "limit": "1",
    })
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado")
    participant = rows[0]
    if participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O vínculo técnico só pode ser aplicado a atletas")

    project_rows = _request("GET", "/rest/v1/agp_projetos_validacao", params={
        "id": f"eq.{participant['projeto_id']}", "select": "instituicao_id", "limit": "1"
    })
    if not isinstance(project_rows, list) or not project_rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Projeto do atleta não localizado")
    institution_id = project_rows[0]["instituicao_id"]

    role_rows = _request("GET", "/rest/v1/agp_papeis_institucionais", params={
        "pessoa_id": f"eq.{technician_id}",
        "instituicao_id": f"eq.{institution_id}",
        "status": "eq.ativo",
        "papel": "in.(tecnico,treinador,preparador_fisico)",
        "select": "id,papel",
        "limit": "1",
    })
    if not isinstance(role_rows, list) or not role_rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O profissional selecionado não possui vínculo técnico ativo com a instituição do atleta")

    previous_id = participant.get("tecnico_responsavel_pessoa_id")
    if str(previous_id or "") == technician_id:
        return {
            "participante_id": str(participante_id),
            "tecnico_responsavel_pessoa_id": technician_id,
            "tecnico_nome": _person_name(technician_id),
            "alterado": False,
        }

    technician_project_rows = _request("GET", "/rest/v1/agp_participantes_projeto", params={
        "projeto_id": f"eq.{participant['projeto_id']}",
        "pessoa_id": f"eq.{technician_id}",
        "ativo": "eq.true",
        "select": "id",
        "limit": "1",
    })
    if not isinstance(technician_project_rows, list) or not technician_project_rows:
        _request("POST", "/rest/v1/agp_participantes_projeto", payload={
            "projeto_id": participant["projeto_id"],
            "pessoa_id": technician_id,
            "funcao_no_projeto": role_rows[0].get("papel") or "tecnico",
            "status_onboarding": "apto_para_coleta",
            "ativo": True,
            "criado_por": str(operator_id),
        })

    now = datetime.now(timezone.utc).isoformat()
    _request("PATCH", "/rest/v1/agp_participantes_projeto", params={"id": f"eq.{participante_id}"}, payload={
        "tecnico_responsavel_pessoa_id": technician_id,
        "updated_at": now,
    })

    _request("POST", "/rest/v1/agp_auditoria_participantes", payload={
        "pessoa_id": participant["pessoa_id"],
        "projeto_id": participant["projeto_id"],
        "acao": "alteracao_tecnico_responsavel",
        "estado_anterior": {
            "participante_id": str(participante_id),
            "tecnico_responsavel_pessoa_id": previous_id,
            "tecnico_nome": _person_name(previous_id),
        },
        "estado_novo": {
            "participante_id": str(participante_id),
            "tecnico_responsavel_pessoa_id": technician_id,
            "tecnico_nome": _person_name(technician_id),
            "motivo": reason,
        },
        "executado_por": str(operator_id),
        "origem": "central_participantes",
    })

    calculated = _request("POST", "/rest/v1/rpc/agp_status_onboarding_participante", payload={"p_participante_id": str(participante_id)})
    onboarding = calculated if isinstance(calculated, str) else participant.get("status_onboarding")
    _request("PATCH", "/rest/v1/agp_participantes_projeto", params={"id": f"eq.{participante_id}"}, payload={
        "status_onboarding": onboarding,
        "updated_at": now,
    })

    return {
        "participante_id": str(participante_id),
        "tecnico_anterior_pessoa_id": previous_id,
        "tecnico_responsavel_pessoa_id": technician_id,
        "tecnico_nome": _person_name(technician_id),
        "status_onboarding": onboarding,
        "alterado": True,
    }


@router.get("/participantes/{participante_id}/historico-tecnicos")
def list_athlete_technician_history(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    participant_rows = _request("GET", "/rest/v1/agp_participantes_projeto", params={
        "id": f"eq.{participante_id}", "select": "pessoa_id,projeto_id", "limit": "1"
    })
    if not isinstance(participant_rows, list) or not participant_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado")
    participant = participant_rows[0]
    rows = _request("GET", "/rest/v1/agp_auditoria_participantes", params={
        "pessoa_id": f"eq.{participant['pessoa_id']}",
        "projeto_id": f"eq.{participant['projeto_id']}",
        "acao": "eq.alteracao_tecnico_responsavel",
        "select": "id,estado_anterior,estado_novo,executado_por,origem,created_at",
        "order": "created_at.desc",
    })
    return rows if isinstance(rows, list) else []
