from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

import requests
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.supabase_client import HEADERS, SUPABASE_KEY, SUPABASE_URL

router = APIRouter(prefix="/api/v1", tags=["participant-onboarding"])

Role = Literal[
    "atleta",
    "tecnico",
    "treinador",
    "preparador_fisico",
    "medico",
    "fisioterapeuta",
    "psicologo",
    "nutricionista",
    "gestor",
    "analista",
    "responsavel_legal",
]


class SportProfileInput(BaseModel):
    modalidade: str = Field(min_length=2, max_length=120)
    prova_posicao: str | None = Field(default=None, max_length=120)
    categoria: str | None = Field(default=None, max_length=120)
    idade_esportiva_anos: float | None = Field(default=None, ge=0, le=80)
    nivel: str | None = Field(default=None, max_length=120)
    equipe: str | None = Field(default=None, max_length=160)
    data_ingresso: date | None = None
    legacy_perfil_atleta_id: UUID | None = None
    dados_complementares: dict[str, Any] = Field(default_factory=dict)


class AccessInput(BaseModel):
    auth_id: UUID | None = None
    email_acesso: EmailStr | None = None


class ParticipantCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    nome_social: str | None = Field(default=None, max_length=200)
    data_nascimento: date | None = None
    email_contato: EmailStr | None = None
    telefone_contato: str | None = Field(default=None, max_length=40)
    documento_referencia: str | None = Field(default=None, max_length=120)
    papel: Role
    projeto_id: UUID | None = None
    tecnico_responsavel_pessoa_id: UUID | None = None
    escopo: dict[str, Any] = Field(default_factory=dict)
    acesso: AccessInput | None = None
    perfil_esportivo: SportProfileInput | None = None

    @model_validator(mode="after")
    def validate_role_requirements(self) -> "ParticipantCreate":
        if self.papel == "atleta" and self.perfil_esportivo is None:
            raise ValueError("perfil_esportivo é obrigatório para atleta")
        if self.tecnico_responsavel_pessoa_id and self.papel != "atleta":
            raise ValueError("técnico responsável só pode ser atribuído a atleta")
        return self


class ParticipantResponse(BaseModel):
    pessoa_id: UUID
    papel_id: UUID
    participante_id: UUID | None = None
    conta_id: UUID | None = None
    perfil_esportivo_id: UUID | None = None
    status_onboarding: str
    pendencias: list[str]


def _request(method: str, path: str, *, payload: Any | None = None, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> Any:
    response = requests.request(
        method,
        f"{SUPABASE_URL}{path}",
        json=payload,
        params=params,
        headers=headers or HEADERS,
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"origem": "supabase", "status": response.status_code, "mensagem": response.text},
        )
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

    rpc_headers = {**auth_headers, "Content-Type": "application/json"}
    is_owner = _request("POST", "/rest/v1/rpc/agp_is_owner", payload={}, headers=rpc_headers)
    if is_owner is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operação restrita ao proprietário Master")
    return UUID(user_id)


def _single_row(rows: Any, entity: str) -> dict[str, Any]:
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Resposta inválida ao criar {entity}")
    return rows[0]


def _delete_created(created: list[tuple[str, UUID]]) -> None:
    for table, row_id in reversed(created):
        try:
            _request("DELETE", f"/rest/v1/{table}", params={"id": f"eq.{row_id}"})
        except Exception:
            pass


def _resolve_institution(project_id: UUID | None, institution_id: UUID) -> None:
    if not project_id:
        return
    rows = _request(
        "GET",
        "/rest/v1/agp_projetos_validacao",
        params={"id": f"eq.{project_id}", "instituicao_id": f"eq.{institution_id}", "select": "id"},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Projeto não pertence à instituição informada")


def _onboarding_status(payload: ParticipantCreate) -> tuple[str, list[str]]:
    pending: list[str] = []
    if not payload.projeto_id:
        pending.append("vinculo_projeto")
    if payload.papel == "atleta":
        if not payload.perfil_esportivo or not payload.perfil_esportivo.legacy_perfil_atleta_id:
            pending.append("perfil_legado_atleta")
        pending.extend(["consentimento", "linha_base"])
    if not payload.acesso or not payload.acesso.auth_id:
        pending.append("conta_acesso")

    if "vinculo_projeto" in pending:
        return "vinculo_pendente", pending
    if "perfil_legado_atleta" in pending:
        return "perfil_pendente", pending
    if "consentimento" in pending:
        return "consentimento_pendente", pending
    if "linha_base" in pending:
        return "linha_base_pendente", pending
    if "conta_acesso" in pending:
        return "acesso_pendente", pending
    return "apto_para_coleta", pending


@router.post(
    "/instituicoes/{instituicao_id}/participantes",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_participant(
    instituicao_id: UUID,
    payload: ParticipantCreate,
    authorization: str | None = Header(default=None),
) -> ParticipantResponse:
    operator_id = _require_owner(authorization)
    _resolve_institution(payload.projeto_id, instituicao_id)

    created: list[tuple[str, UUID]] = []
    onboarding_status, pending = _onboarding_status(payload)

    try:
        person = _single_row(
            _request(
                "POST",
                "/rest/v1/agp_pessoas",
                payload={
                    "nome": payload.nome.strip(),
                    "nome_social": payload.nome_social,
                    "data_nascimento": payload.data_nascimento.isoformat() if payload.data_nascimento else None,
                    "email_contato": str(payload.email_contato) if payload.email_contato else None,
                    "telefone_contato": payload.telefone_contato,
                    "documento_referencia": payload.documento_referencia,
                    "status": "ativo",
                    "criado_por": str(operator_id),
                },
            ),
            "pessoa",
        )
        person_id = UUID(person["id"])
        created.append(("agp_pessoas", person_id))

        role = _single_row(
            _request(
                "POST",
                "/rest/v1/agp_papeis_institucionais",
                payload={
                    "pessoa_id": str(person_id),
                    "instituicao_id": str(instituicao_id),
                    "papel": payload.papel,
                    "escopo": payload.escopo,
                    "status": "ativo",
                    "criado_por": str(operator_id),
                },
            ),
            "papel institucional",
        )
        role_id = UUID(role["id"])
        created.append(("agp_papeis_institucionais", role_id))

        account_id: UUID | None = None
        if payload.acesso:
            account = _single_row(
                _request(
                    "POST",
                    "/rest/v1/agp_contas_acesso",
                    payload={
                        "pessoa_id": str(person_id),
                        "auth_id": str(payload.acesso.auth_id) if payload.acesso.auth_id else None,
                        "email_acesso": str(payload.acesso.email_acesso) if payload.acesso.email_acesso else None,
                        "status": "ativo" if payload.acesso.auth_id else "acesso_pendente",
                    },
                ),
                "conta de acesso",
            )
            account_id = UUID(account["id"])
            created.append(("agp_contas_acesso", account_id))

        sport_profile_id: UUID | None = None
        if payload.perfil_esportivo:
            profile = payload.perfil_esportivo
            sport_profile = _single_row(
                _request(
                    "POST",
                    "/rest/v1/agp_perfis_esportivos",
                    payload={
                        "pessoa_id": str(person_id),
                        "legacy_perfil_atleta_id": str(profile.legacy_perfil_atleta_id) if profile.legacy_perfil_atleta_id else None,
                        "modalidade": profile.modalidade,
                        "prova_posicao": profile.prova_posicao,
                        "categoria": profile.categoria,
                        "idade_esportiva_anos": profile.idade_esportiva_anos,
                        "nivel": profile.nivel,
                        "equipe": profile.equipe,
                        "data_ingresso": profile.data_ingresso.isoformat() if profile.data_ingresso else None,
                        "status": "ativo",
                        "dados_complementares": profile.dados_complementares,
                    },
                ),
                "perfil esportivo",
            )
            sport_profile_id = UUID(sport_profile["id"])
            created.append(("agp_perfis_esportivos", sport_profile_id))

        participant_id: UUID | None = None
        if payload.projeto_id:
            participant = _single_row(
                _request(
                    "POST",
                    "/rest/v1/agp_participantes_projeto",
                    payload={
                        "projeto_id": str(payload.projeto_id),
                        "pessoa_id": str(person_id),
                        "funcao_no_projeto": payload.papel,
                        "tecnico_responsavel_pessoa_id": str(payload.tecnico_responsavel_pessoa_id) if payload.tecnico_responsavel_pessoa_id else None,
                        "status_onboarding": onboarding_status,
                        "ativo": True,
                        "criado_por": str(operator_id),
                    },
                ),
                "participante do projeto",
            )
            participant_id = UUID(participant["id"])
            created.append(("agp_participantes_projeto", participant_id))

        _request(
            "POST",
            "/rest/v1/agp_auditoria_participantes",
            payload={
                "pessoa_id": str(person_id),
                "projeto_id": str(payload.projeto_id) if payload.projeto_id else None,
                "acao": "participante_criado",
                "estado_novo": {
                    "papel": payload.papel,
                    "status_onboarding": onboarding_status,
                    "pendencias": pending,
                },
                "executado_por": str(operator_id),
                "origem": "api_onboarding_v1",
            },
        )

        return ParticipantResponse(
            pessoa_id=person_id,
            papel_id=role_id,
            participante_id=participant_id,
            conta_id=account_id,
            perfil_esportivo_id=sport_profile_id,
            status_onboarding=onboarding_status,
            pendencias=pending,
        )
    except HTTPException:
        _delete_created(created)
        raise
    except Exception as exc:
        _delete_created(created)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha controlada no onboarding: {exc}") from exc


@router.get("/projetos/{projeto_id}/participantes")
def list_project_participants(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_participantes_elegibilidade",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "nome.asc"},
    )
    return rows if isinstance(rows, list) else []
