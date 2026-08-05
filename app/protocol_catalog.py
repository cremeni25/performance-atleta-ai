from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["protocol-catalog"])


class ProtocolInput(BaseModel):
    instituicao_id: UUID | None = None
    codigo: str = Field(min_length=2, max_length=80)
    nome: str = Field(min_length=2, max_length=200)
    dominio: str
    modalidade: str | None = None
    categoria: str | None = None
    versao: str = Field(min_length=1, max_length=40)
    objetivo: str = Field(min_length=2, max_length=2000)
    criterios: dict[str, Any] = {}
    limites_interpretacao: str | None = None
    aprovar: bool = False


class InstrumentInput(BaseModel):
    protocolo_id: UUID
    codigo: str = Field(min_length=2, max_length=80)
    nome: str = Field(min_length=2, max_length=200)
    descricao: str | None = None
    versao: str = Field(min_length=1, max_length=40)
    tipo: str
    respondente: str
    periodicidade: str | None = None
    schema_campos: dict[str, Any] = {}
    regra_completude: dict[str, Any] = {}
    aprovar: bool = False


class ActivationInput(BaseModel):
    instrumento_id: UUID
    instituicao_id: UUID | None = None
    projeto_id: UUID | None = None
    modalidade: str | None = None
    categoria: str | None = None
    versao_configuracao: str = "1.0.0"
    obrigatorio: bool = True
    ordem: int = 0
    periodicidade_override: str | None = None
    configuracao: dict[str, Any] = {}
    data_inicio: date = Field(default_factory=date.today)
    data_fim: date | None = None


@router.get("/catalogo/protocolos")
def list_protocols(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_protocolos", params={"select": "*", "order": "nome.asc,versao.desc"})
    return rows if isinstance(rows, list) else []


@router.post("/catalogo/protocolos", status_code=status.HTTP_201_CREATED)
def create_protocol(payload: ProtocolInput, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    now = datetime.now(timezone.utc).isoformat()
    return _single_row(_request("POST", "/rest/v1/agp_protocolos", payload={
        **payload.model_dump(exclude={"aprovar"}, mode="json"),
        "status_catalogo": "aprovado" if payload.aprovar else "rascunho",
        "ativo": payload.aprovar,
        "criado_por": str(owner_id),
        "aprovado_por": str(owner_id) if payload.aprovar else None,
        "aprovado_em": now if payload.aprovar else None,
        "updated_at": now,
    }), "protocolo")


@router.post("/catalogo/instrumentos", status_code=status.HTTP_201_CREATED)
def create_instrument(payload: InstrumentInput, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    now = datetime.now(timezone.utc).isoformat()
    return _single_row(_request("POST", "/rest/v1/agp_instrumentos", payload={
        **payload.model_dump(exclude={"aprovar"}, mode="json"),
        "status_catalogo": "aprovado" if payload.aprovar else "rascunho",
        "ativo": payload.aprovar,
        "aprovado_por": str(owner_id) if payload.aprovar else None,
        "aprovado_em": now if payload.aprovar else None,
        "updated_at": now,
    }), "instrumento")


@router.get("/projetos/{projeto_id}/catalogo-instrumentos")
def list_project_catalog(projeto_id: UUID, authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_catalogo_instrumentos_operacional", params={
        "or": f"(projeto_id.eq.{projeto_id},and(projeto_id.is.null,instituicao_id.eq.{_project_institution(projeto_id)}))",
        "select": "*",
        "order": "ordem.asc,instrumento_nome.asc",
    })
    return rows if isinstance(rows, list) else []


def _project_institution(projeto_id: UUID) -> str:
    rows = _request("GET", "/rest/v1/agp_projetos_validacao", params={"id": f"eq.{projeto_id}", "select": "instituicao_id"})
    if not rows:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return rows[0]["instituicao_id"]


@router.post("/catalogo/ativacoes", status_code=status.HTTP_201_CREATED)
def activate_instrument(payload: ActivationInput, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    if payload.instituicao_id is None and payload.projeto_id is None:
        raise HTTPException(status_code=422, detail="Informe instituição ou projeto para ativação")
    now = datetime.now(timezone.utc).isoformat()
    return _single_row(_request("POST", "/rest/v1/agp_ativacoes_instrumentos", payload={
        **payload.model_dump(mode="json"),
        "ativo": True,
        "criado_por": str(owner_id),
        "aprovado_por": str(owner_id),
        "aprovado_em": now,
        "updated_at": now,
    }), "ativação de instrumento")
