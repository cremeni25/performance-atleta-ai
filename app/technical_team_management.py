from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import requests
from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.institution_management import _request, _require_owner
from app.owner_activation import _admin_headers, _supabase_url

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


def _canonical_role(role: str) -> str:
    return {
        "admin_institucional": "gestor",
        "tecnico": "tecnico",
        "assistente": "analista",
        "observador": "analista",
    }.get(role, "tecnico")


def _ensure_canonical_person(member: dict[str, Any], operator_id: UUID) -> UUID:
    auth_id = str(member.get("auth_id") or "").strip()
    institution_id = str(member.get("instituicao_id") or "").strip()
    if not auth_id or not institution_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vínculo técnico sem usuário ou instituição")

    account_rows = _request(
        "GET",
        "/rest/v1/agp_contas_acesso",
        params={"auth_id": f"eq.{auth_id}", "select": "id,pessoa_id", "limit": "1"},
    )

    if isinstance(account_rows, list) and account_rows:
        person_id = UUID(account_rows[0]["pessoa_id"])
    else:
        email = str(member.get("email") or "").strip() or None
        person_rows: list[dict[str, Any]] = []
        if email:
            result = _request(
                "GET",
                "/rest/v1/agp_pessoas",
                params={"email_contato": f"eq.{email}", "select": "id", "limit": "1"},
            )
            person_rows = result if isinstance(result, list) else []

        if person_rows:
            person_id = UUID(person_rows[0]["id"])
        else:
            created = _request(
                "POST",
                "/rest/v1/agp_pessoas",
                payload={
                    "nome": str(member.get("nome") or email or auth_id).strip(),
                    "email_contato": email,
                    "status": "ativo",
                    "criado_por": str(operator_id),
                },
            )
            if not isinstance(created, list) or len(created) != 1:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao criar identidade canônica do profissional")
            person_id = UUID(created[0]["id"])

        account = _request(
            "POST",
            "/rest/v1/agp_contas_acesso",
            payload={
                "pessoa_id": str(person_id),
                "auth_id": auth_id,
                "email_acesso": email,
                "status": "ativo",
            },
        )
        if not isinstance(account, list) or len(account) != 1:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao vincular acesso canônico do profissional")

    canonical_role = _canonical_role(str(member.get("papel") or "tecnico"))
    role_rows = _request(
        "GET",
        "/rest/v1/agp_papeis_institucionais",
        params={
            "pessoa_id": f"eq.{person_id}",
            "instituicao_id": f"eq.{institution_id}",
            "papel": f"eq.{canonical_role}",
            "select": "id",
            "limit": "1",
        },
    )
    if not isinstance(role_rows, list) or not role_rows:
        created_role = _request(
            "POST",
            "/rest/v1/agp_papeis_institucionais",
            payload={
                "pessoa_id": str(person_id),
                "instituicao_id": institution_id,
                "papel": canonical_role,
                "escopo": {"origem": "nucleo_administrativo", "membro_instituicao_id": member.get("id")},
                "status": "ativo" if member.get("ativo") is not False else "suspenso",
                "criado_por": str(operator_id),
            },
        )
        if not isinstance(created_role, list) or len(created_role) != 1:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao criar papel institucional canônico")

    return person_id


@router.get("/equipe-tecnica/usuarios")
def list_auth_users(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    users: list[dict[str, Any]] = []
    for page in range(1, 101):
        response = requests.get(
            f"{_supabase_url()}/auth/v1/admin/users",
            headers=_admin_headers(),
            params={"page": page, "per_page": 1000},
            timeout=20,
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Não foi possível consultar os usuários autenticados do AGP")
        payload = response.json()
        page_users = payload.get("users", []) if isinstance(payload, dict) else []
        for user in page_users:
            metadata = user.get("user_metadata") or {}
            email = str(user.get("email") or "").strip()
            nome = str(metadata.get("nome") or metadata.get("name") or metadata.get("full_name") or email or user.get("id") or "").strip()
            users.append({
                "id": user.get("id"),
                "auth_id": user.get("id"),
                "nome": nome,
                "email": email or None,
                "tipo_usuario": metadata.get("tipo_usuario"),
                "confirmado": bool(user.get("email_confirmed_at")),
            })
        if len(page_users) < 1000:
            break
    return sorted(users, key=lambda item: str(item.get("nome") or "").lower())


@router.get("/equipe-tecnica")
def list_technical_team(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_membros_instituicao", params={
        "select": "*,instituicao:agp_instituicoes(id,nome,slug)",
        "papel": "in.(admin_institucional,tecnico,assistente,observador)",
        "order": "nome.asc"
    })
    return rows if isinstance(rows, list) else []


@router.get("/equipe-tecnica/canonicos")
def list_canonical_technical_team(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    operator_id = _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_membros_instituicao", params={
        "select": "*,instituicao:agp_instituicoes(id,nome,slug)",
        "papel": "in.(admin_institucional,tecnico,assistente,observador)",
        "ativo": "eq.true",
        "order": "nome.asc"
    })
    members = rows if isinstance(rows, list) else []
    result: list[dict[str, Any]] = []
    for member in members:
        person_id = _ensure_canonical_person(member, operator_id)
        result.append({**member, "pessoa_id": str(person_id), "papel_canonico": _canonical_role(str(member.get("papel") or "tecnico"))})
    return result


@router.post("/equipe-tecnica", status_code=status.HTTP_201_CREATED)
def create_technical_member(payload: TechnicalMemberCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
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
    member = rows[0]
    person_id = _ensure_canonical_person(member, operator_id)
    return {**member, "pessoa_id": str(person_id)}


@router.patch("/equipe-tecnica/{membro_id}")
def update_technical_member(membro_id: UUID, payload: TechnicalMemberUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
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
    member = rows[0]
    person_id = _ensure_canonical_person(member, operator_id)
    return {**member, "pessoa_id": str(person_id)}


@router.delete("/equipe-tecnica/{membro_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technical_member(membro_id: UUID, authorization: str | None = Header(default=None)) -> Response:
    _require_owner(authorization)
    _request("DELETE", "/rest/v1/agp_membros_instituicao", params={"id": f"eq.{membro_id}"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
