from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import (
    _actor_person,
    _authorize_individual_read,
    _target_participant,
)

router = APIRouter(prefix="/api/v1", tags=["integrative-ai-governance"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


@router.get("/participantes/{participante_id}/ia-integrativa/contexto")
def integrative_ai_context(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Prepare the authorized, traceable evidence envelope for future integrative AI.

    This endpoint does not call a generative model. It proves what the model would be
    allowed to see and returns dados_insuficientes when canonical evidence is not ready.
    """
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    access = _authorize_individual_read(str(actor["pessoa_id"]), participant)
    pessoa_id = str(participant["pessoa_id"])

    state = _first(
        _request(
            "GET",
            "/rest/v1/agp_estado_longitudinal_individual",
            params={"pessoa_id": f"eq.{pessoa_id}", "select": "*", "limit": "1"},
        )
    ) or {"pessoa_id": pessoa_id, "estado": "sem_evidencia_longitudinal"}

    series = _rows(
        _request(
            "GET",
            "/rest/v1/agp_series_longitudinais_metricas_v2",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "select": "metrica_id,metrica_codigo,nome_canonico,dominio,amostras,primeira_medicao_em,ultima_medicao_em,completude_media,confiabilidade_media,primeiro_valor,ultimo_valor,unidade_atual,estado_comparabilidade,delta_absoluto,delta_percentual",
                "order": "dominio.asc,metrica_codigo.asc",
            },
        )
    )

    comparable = [row for row in series if row.get("estado_comparabilidade") == "comparavel"]
    metric_ids = [str(row["metrica_id"]) for row in comparable if row.get("metrica_id")]

    scientific_sources: list[dict[str, Any]] = []
    if metric_ids:
        relations = _rows(
            _request(
                "GET",
                "/rest/v1/agp_metrica_fontes",
                params={
                    "metrica_id": f"in.({','.join(metric_ids)})",
                    "select": "metrica_id,fonte_id,justificativa",
                },
            )
        )
        source_ids = sorted({str(row["fonte_id"]) for row in relations if row.get("fonte_id")})
        sources_by_id: dict[str, dict[str, Any]] = {}
        if source_ids:
            sources = _rows(
                _request(
                    "GET",
                    "/rest/v1/agp_fontes_cientificas",
                    params={
                        "id": f"in.({','.join(source_ids)})",
                        "select": "id,titulo,autores,organizacao,ano,tipo,doi,url,nivel_evidencia,status_validacao",
                    },
                )
            )
            sources_by_id = {str(row["id"]): row for row in sources if row.get("id")}
        scientific_sources = [
            {
                "metrica_id": row.get("metrica_id"),
                "justificativa": row.get("justificativa"),
                "fonte": sources_by_id.get(str(row.get("fonte_id"))),
            }
            for row in relations
            if sources_by_id.get(str(row.get("fonte_id")))
        ]

    cycles = _rows(
        _request(
            "GET",
            "/rest/v1/agp_ciclos_longitudinais",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "select": "id,nivel,codigo,nome,objetivo,inicio,fim,status,versao",
                "order": "inicio.desc",
                "limit": "30",
            },
        )
    )
    milestones = _rows(
        _request(
            "GET",
            "/rest/v1/agp_marcos_longitudinais",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "select": "id,tipo,ocorrido_em,titulo,descricao,origem,contexto",
                "order": "ocorrido_em.desc",
                "limit": "30",
            },
        )
    )

    ready = bool(comparable)
    return {
        "modelo_governanca": "AGP-Integrative-AI-Governance-v1",
        "execucao_modelo_realizada": False,
        "estado_preparacao": "pronta_execucao" if ready else "dados_insuficientes",
        "acesso": access,
        "participante_id": str(participante_id),
        "pessoa_id": pessoa_id,
        "estado_longitudinal": state,
        "evidencias_autorizadas": {
            "series_comparaveis": comparable,
            "ciclos": cycles,
            "marcos": milestones,
            "fontes_cientificas_relacionadas": scientific_sources,
        },
        "evidencias_excluidas": [
            {
                "metrica_codigo": row.get("metrica_codigo"),
                "motivo": row.get("estado_comparabilidade"),
            }
            for row in series
            if row.get("estado_comparabilidade") != "comparavel"
        ],
        "regras_obrigatorias_saida": [
            "Separar fato, inferencia, hipotese e suporte_decisao.",
            "Citar a evidencia interna e a fonte cientifica utilizada quando aplicavel.",
            "Declarar confianca e limitacoes.",
            "Nao converter delta em melhora ou piora sem regra cientifica especifica da metrica.",
            "Nao inferir causalidade por proximidade temporal.",
            "Nao emitir diagnostico clinico.",
            "Exigir validacao profissional quando a conclusao ultrapassar o escopo tecnico autorizado.",
            "Retornar dados_insuficientes em vez de completar lacunas por suposicao.",
        ],
    }
