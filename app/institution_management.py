from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

import requests
from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.supabase_client import HEADERS, SUPABASE_KEY, SUPABASE_URL

router = APIRouter(prefix="/api/v1/administracao", tags=["administracao-instituicoes"])

InstitutionType = Literal["homologacao", "clube", "associacao", "instituto", "academia"]
InstitutionStatus = Literal["ativo", "suspenso", "encerrado"]


class InstitutionCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    tipo: InstitutionType = "instituto"
    localidade: str | None = Field(default=None, max_length=200)
    status: InstitutionStatus = "ativo"


class InstitutionUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=200)
    tipo: InstitutionType | None = None
    localidade: str | None = Field(default=None, max_length=200)
    status: InstitutionStatus | None = None


def _request(method: str, path: str, *, payload: Any | None = None, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> Any:
    response = requests.request(method, f"{SUPABASE_URL}{path}", json=payload, params=params, headers=headers or HEADERS, timeout=20)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"origem": "supabase", "status": response.status_code, "mensagem": response.text})
    if not response.content:
        return None
    return response.json()


def _require_owner(authorization: str | None) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso ausente")
    token = authorization.split(" ", 1)[1].strip()
    auth_headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"}
    user = _request("GET", "/auth/v1/user", headers=auth_headers)
    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")
    is_owner = _request("POST", "/rest/v1/rpc/agp_is_owner", payload={}, headers={**auth_headers, "Content-Type": "application/json"})
    if is_owner is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operação restrita ao proprietário Master")
    return UUID(user_id)


def _slugify(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


@router.get("/instituicoes")
def list_institutions(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_instituicoes", params={"select": "*", "order": "nome.asc"})
    return rows if isinstance(rows, list) else []


@router.post("/instituicoes", status_code=status.HTTP_201_CREATED)
def create_institution(payload: InstitutionCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    slug = _slugify(payload.slug or payload.nome)
    if not slug:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug inválido")
    rows = _request("POST", "/rest/v1/agp_instituicoes", payload={"nome": payload.nome.strip(), "slug": slug, "tipo": payload.tipo, "localidade": payload.localidade or None, "status": payload.status, "criado_por": str(operator_id)})
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Resposta inválida ao criar instituição")
    return rows[0]


@router.patch("/instituicoes/{instituicao_id}")
def update_institution(instituicao_id: UUID, payload: InstitutionUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    changes = payload.dict(exclude_unset=True)
    if "nome" in changes and changes["nome"] is not None:
        changes["nome"] = changes["nome"].strip()
    if "slug" in changes and changes["slug"] is not None:
        changes["slug"] = _slugify(changes["slug"])
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteração informada")
    rows = _request("PATCH", "/rest/v1/agp_instituicoes", params={"id": f"eq.{instituicao_id}"}, payload=changes)
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instituição não encontrada")
    return rows[0]


@router.delete("/instituicoes/{instituicao_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_institution(instituicao_id: UUID, authorization: str | None = Header(default=None)) -> Response:
    _require_owner(authorization)
    _request("DELETE", "/rest/v1/agp_instituicoes", params={"id": f"eq.{instituicao_id}"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
