from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request

router = APIRouter(prefix="/api/v1", tags=["canonical-institutional-intelligence"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _actor_person(user_id: str) -> dict[str, Any]:
    account = _first(
        _request(
            "GET",
            "/rest/v1/agp_contas_acesso",
            params={
                "auth_id": f"eq.{user_id}",
                "status": "eq.ativo",
                "select": "id,pessoa_id,status",
                "limit": "1",
            },
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Identidade AGP ativa não encontrada")
    return account


def _capability_codes(contexts: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("codigo")
        for row in contexts
        for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }


def _authorize_scope(actor_pessoa_id: str, instituicao_id: UUID) -> dict[str, Any]:
    contexts = _rows(
        _request(
            "GET",
            "/rest/v1/agp_contextos_identidade_efetivos",
            params={
                "pessoa_id": f"eq.{actor_pessoa_id}",
                "instituicao_id": f"eq.{instituicao_id}",
                "status": "eq.ativo",
                "select": "instituicao_id,projeto_id,papel_codigo,familia,capacidades",
            },
        )
    )
    capabilities = _capability_codes(contexts)
    if "platform.govern" in capabilities or "institution.aggregate_read" in capabilities:
        return {
            "modo": "institucional",
            "capacidades": sorted(capabilities),
            "projetos_permitidos": None,
        }

    technical_allowed = {"analysis.performance", "decision.technical", "training.plan", "evidence.review_technical"}
    granted = sorted(capabilities.intersection(technical_allowed))
    project_ids = sorted({str(row["projeto_id"]) for row in contexts if row.get("projeto_id")})
    if granted and project_ids:
        return {
            "modo": "projetos_vinculados",
            "capacidades": granted,
            "projetos_permitidos": project_ids,
        }

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Papel atual não possui escopo para inteligência institucional desta instituição",
    )


def _operational_message(summary: dict[str, Any] | None) -> dict[str, str]:
    state = (summary or {}).get("estado_operacional")
    if state == "longitudinalidade_em_operacao":
        return {
            "estado": state,
            "significado": "Há atletas com evidência longitudinal observável no escopo autorizado.",
            "proxima_acao": "Usar os agregados para organizar atenção e recursos sem substituir a leitura individual.",
        }
    if state == "evidencia_em_formacao":
        return {
            "estado": state,
            "significado": "Já existe evidência validada, mas a longitudinalidade coletiva ainda está em formação.",
            "proxima_acao": "Manter continuidade de coleta e consistência de protocolos antes de conclusões agregadas.",
        }
    if state == "sem_atletas_ativos":
        return {
            "estado": state,
            "significado": "Não há atletas ativos no escopo institucional atual.",
            "proxima_acao": "Não produzir inteligência esportiva até existir população operacional ativa.",
        }
    return {
        "estado": state or "aguardando_evidencia_operacional",
        "significado": "O escopo ainda não possui evidência operacional suficiente para inteligência longitudinal agregada.",
        "proxima_acao": "Priorizar operação e evidência real; não criar ranking ou score substituto.",
    }


@router.get("/instituicoes/{instituicao_id}/inteligencia-canonica")
def canonical_institutional_intelligence(
    instituicao_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    access = _authorize_scope(str(actor["pessoa_id"]), instituicao_id)

    institution = _first(
        _request(
            "GET",
            "/rest/v1/agp_instituicoes",
            params={
                "id": f"eq.{instituicao_id}",
                "select": "id,nome,nome_exibicao,tipo,localidade,status",
                "limit": "1",
            },
        )
    )
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instituição não encontrada")

    project_rows = _rows(
        _request(
            "GET",
            "/rest/v1/agp_inteligencia_projeto_canonica",
            params={
                "instituicao_id": f"eq.{instituicao_id}",
                "select": "*",
                "order": "projeto_nome.asc",
            },
        )
    )

    allowed_projects = access.get("projetos_permitidos")
    if isinstance(allowed_projects, list):
        project_rows = [row for row in project_rows if str(row.get("projeto_id")) in allowed_projects]
        institution_summary = None
    else:
        institution_summary = _first(
            _request(
                "GET",
                "/rest/v1/agp_inteligencia_institucional_canonica",
                params={
                    "instituicao_id": f"eq.{instituicao_id}",
                    "select": "*",
                    "limit": "1",
                },
            )
        )

    attention = []
    for project in project_rows:
        if int(project.get("atletas_sem_evidencia_longitudinal") or 0) > 0:
            attention.append({
                "projeto_id": project.get("projeto_id"),
                "tipo": "cobertura_longitudinal",
                "quantidade": project.get("atletas_sem_evidencia_longitudinal"),
                "mensagem": "Há atletas ativos ainda sem evidência longitudinal observável.",
            })
        if int(project.get("series_metricas_requerendo_revisao") or 0) > 0:
            attention.append({
                "projeto_id": project.get("projeto_id"),
                "tipo": "qualidade_comparabilidade",
                "quantidade": project.get("series_metricas_requerendo_revisao"),
                "mensagem": "Existem séries métricas que exigem revisão de comparabilidade.",
            })
        if int(project.get("sessoes_abertas") or 0) > 0:
            attention.append({
                "projeto_id": project.get("projeto_id"),
                "tipo": "operacao_aberta",
                "quantidade": project.get("sessoes_abertas"),
                "mensagem": "Existem sessões planejadas ou em execução no escopo atual.",
            })

    return {
        "modelo": "AGP-Institutional-Intelligence-v1",
        "principio": "inteligencia_coletiva_sem_apagar_o_individuo",
        "acesso": access,
        "instituicao": institution,
        "resumo_institucional": institution_summary,
        "projetos": project_rows,
        "atencoes_operacionais": attention,
        "devolucao_operacional": _operational_message(institution_summary or (project_rows[0] if len(project_rows) == 1 else None)),
        "limites": [
            "O agregado institucional não substitui a leitura longitudinal individual.",
            "Não existe ranking canônico de atletas por score global.",
            "Ausência de evidência não é desempenho ruim; é insuficiência de observação.",
            "Comparações coletivas exigem equivalência de contexto, protocolo e população.",
            "Informação clínica ou regulada permanece no escopo do profissional competente.",
        ],
    }
