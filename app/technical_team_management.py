from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.institution_management import _request, _require_owner

router = APIRouter(prefix="/api/v1/administracao", tags=["administracao-equipe-tecnica"])

TechnicalRole = Literal["admin_institucional", "tecnico", "assistente", "observador"]


class TechnicalMemberCreate(BaseModel):
    instituicao_id: UUID
    auth_id: UUID
    nome: str = Field(min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    papel: TechnicalRole = "tecnico"
    acesso_total_tecnico: bool = False
    ativo: bool = True


class TechnicalMemberUpdate(BaseModel):
    instituicao_id: UUID | None = None
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    papel: TechnicalRole | None = None
    acesso_total_tecnico: bool | None = None
    ativo: bool | None = None


def _institution_exists(institution_id: UUID) -> None:
    rows = _request("GET", "/rest/v1/agp_instituicoes", params={"id": f"eq.{institution_id}", "select": "id", "limit": "1"})
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Instituição não encontrada")


@router.get("/equipe-tecnica")
def list_technical_team(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_membros_instituicao", params={
        "select": "*,instituicao:agp_instituicoes(id,nome,slug)",
        "papel": "in.(admin_institucional,tecnico,assistente,observador)",
        "order": "nome.asc"
    })
    return rows if isinstance(rows, list) else []


@router.post("/equipe-tecnica", status_code=status.HTTP_201_CREATED)
def create_technical_member(payload: TechnicalMemberCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    _institution_exists(payload.instituicao_id)
    rows = _request("POST", "/rest/v1/agp_membros_instituicao", payload={
        "instituicao_id": str(payload.instituicao_id),
        "auth_id": str(payload.auth_id),
        "nome": payload.nome.strip(),
        "email": payload.email.strip() if payload.email else None,
        "papel": payload.papel,
        "acesso_total_tecnico": payload.acesso_total_tecnico,
        "ativo": payload.ativo
    })
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Resposta inválida ao criar membro técnico")
    return rows[0]


@router.patch("/equipe-tecnica/{membro_id}")
def update_technical_member(membro_id: UUID, payload: TechnicalMemberUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    changes = payload.dict(exclude_unset=True)
    if "instituicao_id" in changes and changes["instituicao_id"] is not None:
        _institution_exists(changes["instituicao_id"])
        changes["instituicao_id"] = str(changes["instituicao_id"])
    if "nome" in changes and changes["nome"] is not None:
        changes["nome"] = changes["nome"].strip()
    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].strip()
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteração informada")
    rows = _request("PATCH", "/rest/v1/agp_membros_instituicao", params={"id": f"eq.{membro_id}"}, payload=changes)
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membro técnico não encontrado")
    return rows[0]


@router.delete("/equipe-tecnica/{membro_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technical_member(membro_id: UUID, authorization: str | None = Header(default=None)) -> Response:
    _require_owner(authorization)
    _request("DELETE", "/rest/v1/agp_membros_instituicao", params={"id": f"eq.{membro_id}"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
