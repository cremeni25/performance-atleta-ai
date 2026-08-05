from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["collection-instances"])


class CollectionCreate(BaseModel):
    participante_id: UUID
    ativacao_instrumento_id: UUID
    instrumento_id: UUID
    protocolo_id: UUID | None = None
    origem: str
    papel_coletor: str
    ciclo_referencia: str | None = None
    janela_inicio: datetime | None = None
    janela_fim: datetime | None = None
    versao_schema: str = "1.0.0"
    dados: dict[str, Any] = {}


class CollectionUpdate(BaseModel):
    dados: dict[str, Any]
    status: str = Field(pattern="^(rascunho|completa|validada|rejeitada|corrigida)$")
    justificativa_correcao: str | None = None


def _participant(participante_id: UUID) -> dict[str, Any]:
    rows = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}", "select": "id,projeto_id,pessoa_id"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Participante não encontrado")
    participant = rows[0]
    profiles = _request(
        "GET",
        "/rest/v1/agp_perfis_esportivos",
        params={"pessoa_id": f"eq.{participant['pessoa_id']}", "select": "legacy_perfil_atleta_id"},
    )
    if not profiles or not profiles[0].get("legacy_perfil_atleta_id"):
        raise HTTPException(status_code=422, detail="Perfil esportivo legado não vinculado")
    participant["atleta_id"] = profiles[0]["legacy_perfil_atleta_id"]
    return participant


@router.get("/projetos/{projeto_id}/coletas")
def list_project_collections(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_coletas_operacionais",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "data_hora_coleta.desc"},
    )
    return rows if isinstance(rows, list) else []


@router.post("/coletas", status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    participant = _participant(payload.participante_id)
    now = datetime.now(timezone.utc).isoformat()
    row = {
        **payload.model_dump(mode="json"),
        "atleta_id": participant["atleta_id"],
        "projeto_id": participant["projeto_id"],
        "coletado_por_auth_id": str(owner_id),
        "data_hora_coleta": now,
        "iniciado_em": now,
        "status": "rascunho",
    }
    return _single_row(_request("POST", "/rest/v1/agp_coletas", payload=row), "coleta")


@router.patch("/coletas/{coleta_id}")
def update_collection(
    coleta_id: UUID,
    payload: CollectionUpdate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    update = payload.model_dump(mode="json")
    if payload.status == "validada":
        update["validado_por_auth_id"] = str(owner_id)
        update["validado_em"] = datetime.now(timezone.utc).isoformat()
    return _single_row(
        _request("PATCH", "/rest/v1/agp_coletas", params={"id": f"eq.{coleta_id}"}, payload=update),
        "coleta",
    )


@router.get("/coletas/{coleta_id}/versoes")
def list_collection_versions(
    coleta_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_respostas_coleta_versoes",
        params={"coleta_id": f"eq.{coleta_id}", "select": "*", "order": "numero_versao.desc"},
    )
    return rows if isinstance(rows, list) else []
