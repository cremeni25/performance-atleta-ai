from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from app.participant_onboarding import _request
from app.supabase_client import SUPABASE_KEY

router = APIRouter(prefix="/api/v1", tags=["identity-context"])


def _authenticated_user(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso ausente")

    token = authorization.split(" ", 1)[1].strip()
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"}
    user = _request("GET", "/auth/v1/user", headers=headers)
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")
    return user


def _first(rows: Any) -> dict[str, Any] | None:
    if isinstance(rows, list) and rows:
        return rows[0]
    return None


@router.get("/identidade/contexto")
def get_identity_context(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return the canonical multi-role identity context for the signed-in AGP person.

    This endpoint is intentionally UI-agnostic. It resolves one identity into all active
    institution/project roles, capabilities, competencies and sport contexts so later
    workspaces do not collapse a person into a single userType.
    """

    user = _authenticated_user(authorization)
    auth_id = str(user["id"])

    account = _first(
        _request(
            "GET",
            "/rest/v1/agp_contas_acesso",
            params={
                "auth_id": f"eq.{auth_id}",
                "status": "eq.ativo",
                "select": "id,pessoa_id,auth_id,status",
                "limit": "1",
            },
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identidade AGP ativa não encontrada")

    pessoa_id = str(account["pessoa_id"])
    person = _first(
        _request(
            "GET",
            "/rest/v1/agp_pessoas",
            params={"id": f"eq.{pessoa_id}", "select": "id,nome,nome_social,status", "limit": "1"},
        )
    )
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pessoa AGP não encontrada")

    contexts = _request(
        "GET",
        "/rest/v1/agp_contextos_identidade_efetivos",
        params={
            "pessoa_id": f"eq.{pessoa_id}",
            "select": "pessoa_id,instituicao_id,projeto_id,papel_codigo,familia,papel_nome_canonico,requer_credencial_profissional,status,data_inicio,data_fim,origem,capacidades,competencias",
            "order": "familia.asc,papel_codigo.asc,projeto_id.asc.nullsfirst",
        },
    )
    if not isinstance(contexts, list):
        contexts = []

    project_ids = sorted({str(row["projeto_id"]) for row in contexts if row.get("projeto_id")})
    sport_contexts: list[dict[str, Any]] = []

    for project_id in project_ids:
        global_context = _first(
            _request(
                "GET",
                "/rest/v1/agp_contextos_globais_projeto",
                params={
                    "projeto_id": f"eq.{project_id}",
                    "select": "projeto_id,perfil_especializacao_id,locale_codigo,pais_codigo,timezone,sistema_unidades,configuracao_local",
                    "limit": "1",
                },
            )
        )

        project = _first(
            _request(
                "GET",
                "/rest/v1/agp_projetos_validacao",
                params={"id": f"eq.{project_id}", "select": "id,instituicao_id,nome,status", "limit": "1"},
            )
        )

        profile = None
        if global_context and global_context.get("perfil_especializacao_id"):
            profile = _first(
                _request(
                    "GET",
                    "/rest/v1/agp_perfis_especializacao_esportiva",
                    params={
                        "id": f"eq.{global_context['perfil_especializacao_id']}",
                        "select": "id,codigo,versao,status_catalogo,esporte_id,modalidade_id",
                        "limit": "1",
                    },
                )
            )

        sport_contexts.append(
            {
                "projeto": project,
                "contexto_global": global_context,
                "perfil_esportivo": profile,
            }
        )

    capability_codes = sorted(
        {
            item.get("codigo")
            for row in contexts
            for item in (row.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
    )

    required_credential_gaps = []
    for row in contexts:
        for competence in row.get("competencias") or []:
            if not isinstance(competence, dict):
                continue
            if competence.get("requer_credencial_regulada") and not competence.get("credencial_verificada"):
                required_credential_gaps.append(
                    {
                        "papel_codigo": row.get("papel_codigo"),
                        "instituicao_id": row.get("instituicao_id"),
                        "projeto_id": row.get("projeto_id"),
                        "competencia_codigo": competence.get("codigo"),
                    }
                )

    return {
        "identidade": {
            "pessoa_id": pessoa_id,
            "nome": person.get("nome_social") or person.get("nome"),
            "status": person.get("status"),
            "auth_id": auth_id,
            "conta_id": account.get("id"),
        },
        "papeis_ativos": contexts,
        "capacidades_efetivas": capability_codes,
        "contextos_esportivos": sport_contexts,
        "pendencias_credenciais_reguladas": required_credential_gaps,
        "modelo": "one_identity_multi_role_scoped_capabilities_v1",
    }
