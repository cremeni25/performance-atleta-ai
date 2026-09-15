from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, ValidationError

from app.institution_management import _request, _require_owner

router = APIRouter(prefix="/api/v1/administracao", tags=["administracao-projetos"])

ProjectStatus = Literal["preparacao", "homologacao", "em_campo", "concluido", "suspenso"]


class ProjectCreate(BaseModel):
    instituicao_id: UUID
    nome: str = Field(min_length=2, max_length=200)
    objetivo: str = Field(min_length=2, max_length=2000)
    metodologia: str | None = Field(default=None, max_length=4000)
    diretrizes: str | None = Field(default=None, max_length=4000)
    localidade: str | None = Field(default=None, max_length=200)
    data_inicio: date | None = None
    data_fim: date | None = None
    status: ProjectStatus = "preparacao"
    versao_motor: str = Field(default="agp-core-v2", min_length=2, max_length=100)


class ProjectUpdate(BaseModel):
    instituicao_id: UUID | None = None
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    objetivo: str | None = Field(default=None, min_length=2, max_length=2000)
    metodologia: str | None = Field(default=None, max_length=4000)
    diretrizes: str | None = Field(default=None, max_length=4000)
    localidade: str | None = Field(default=None, max_length=200)
    data_inicio: date | None = None
    data_fim: date | None = None
    status: ProjectStatus | None = None
    versao_motor: str | None = Field(default=None, min_length=2, max_length=100)


def _validate_dates(data_inicio: date | None, data_fim: date | None) -> None:
    if data_inicio and data_fim and data_fim < data_inicio:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A data final não pode ser anterior à data inicial")


def _ensure_institution(instituicao_id: UUID) -> None:
    rows = _request("GET", "/rest/v1/agp_instituicoes", params={"id": f"eq.{instituicao_id}", "select": "id", "limit": "1"})
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Instituição não encontrada")


def _project_create_from_raw(raw: dict[str, Any]) -> ProjectCreate:
    allowed = {
        "instituicao_id",
        "nome",
        "objetivo",
        "metodologia",
        "diretrizes",
        "localidade",
        "data_inicio",
        "data_fim",
        "status",
        "versao_motor",
    }
    clean = {key: raw.get(key) for key in allowed if key in raw}
    for field in ("metodologia", "diretrizes", "localidade", "data_inicio", "data_fim"):
        if clean.get(field) == "":
            clean[field] = None
    for field in ("nome", "objetivo", "metodologia", "diretrizes", "localidade", "versao_motor"):
        if isinstance(clean.get(field), str):
            clean[field] = clean[field].strip()
    try:
        return ProjectCreate(**clean)
    except ValidationError as exc:
        messages: list[str] = []
        for item in exc.errors():
            loc = ".".join(str(part) for part in item.get("loc", [])) or "campo"
            messages.append(f"{loc}: {item.get('msg', 'valor inválido')}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=" | ".join(messages) or "Dados do projeto inválidos",
        ) from exc


@router.get("/projetos")
def list_projects(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_projetos_validacao",
        params={"select": "*,instituicao:agp_instituicoes(id,nome,slug)", "order": "created_at.desc"},
    )
    return rows if isinstance(rows, list) else []


@router.post("/projetos", status_code=status.HTTP_201_CREATED)
def create_project(payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    project = _project_create_from_raw(payload)
    _ensure_institution(project.instituicao_id)
    _validate_dates(project.data_inicio, project.data_fim)
    data = project.dict()
    data["instituicao_id"] = str(project.instituicao_id)
    data["data_inicio"] = project.data_inicio.isoformat() if project.data_inicio else None
    data["data_fim"] = project.data_fim.isoformat() if project.data_fim else None
    data["nome"] = project.nome.strip()
    data["objetivo"] = project.objetivo.strip()
    rows = _request("POST", "/rest/v1/agp_projetos_validacao", payload=data)
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Resposta inválida ao criar projeto")
    return rows[0]


@router.patch("/projetos/{projeto_id}")
def update_project(projeto_id: UUID, payload: ProjectUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    changes = payload.dict(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteração informada")
    if changes.get("instituicao_id"):
        _ensure_institution(changes["instituicao_id"])
        changes["instituicao_id"] = str(changes["instituicao_id"])
    for field in ("data_inicio", "data_fim"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].isoformat()
    current = _request("GET", "/rest/v1/agp_projetos_validacao", params={"id": f"eq.{projeto_id}", "select": "data_inicio,data_fim", "limit": "1"})
    if not isinstance(current, list) or not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado")
    start_value = changes.get("data_inicio", current[0].get("data_inicio"))
    end_value = changes.get("data_fim", current[0].get("data_fim"))
    _validate_dates(date.fromisoformat(start_value) if start_value else None, date.fromisoformat(end_value) if end_value else None)
    if "nome" in changes and changes["nome"] is not None:
        changes["nome"] = changes["nome"].strip()
    if "objetivo" in changes and changes["objetivo"] is not None:
        changes["objetivo"] = changes["objetivo"].strip()
    rows = _request("PATCH", "/rest/v1/agp_projetos_validacao", params={"id": f"eq.{projeto_id}"}, payload=changes)
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado")
    return rows[0]


@router.delete("/projetos/{projeto_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(projeto_id: UUID, authorization: str | None = Header(default=None)) -> Response:
    _require_owner(authorization)
    _request("DELETE", "/rest/v1/agp_projetos_validacao", params={"id": f"eq.{projeto_id}"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
