from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import (
    _actor_person,
    _authorize_individual_read,
    _target_participant,
)

router = APIRouter(prefix="/api/v1", tags=["canonical-analytic-engine"])

ENGINE_VERSION = "AGP-CANONICAL-EVIDENCE-1.0.0"


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _latest_baselines(participante_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_linhas_base_canonicas", params={
        "participante_id": f"eq.{participante_id}",
        "select": (
            "id,categoria,idade_cronologica,idade_calculada_em,modalidade,prova_posicao,"
            "classificacao_maturacional,metodo_maturacional,versao_maturacao,"
            "offset_maturacional_anos,idade_pico_velocidade_anos,data_referencia,"
            "origem,status,completude"
        ),
        "order": "data_referencia.desc",
        "limit": "2",
    }))


def _maturation_context(baselines: list[dict[str, Any]]) -> dict[str, Any]:
    if not baselines:
        return {
            "estado": "dados_insuficientes",
            "atual": None,
            "anterior": None,
            "mudancas_contextuais": [],
        }
    current = baselines[0]
    previous = baselines[1] if len(baselines) > 1 else None
    changes: list[dict[str, Any]] = []
    if previous:
        for field in ("categoria", "classificacao_maturacional", "modalidade", "prova_posicao"):
            if current.get(field) != previous.get(field):
                changes.append({
                    "campo": field,
                    "anterior": previous.get(field),
                    "atual": current.get(field),
                    "significado": "mudanca_de_contexto_nao_causal",
                })
    return {
        "estado": "contexto_disponivel",
        "atual": current,
        "anterior": previous,
        "mudancas_contextuais": changes,
        "regra": "crescimento_maturacao_e_categoria_contextualizam_comparacoes_mas_nao_provam_causalidade",
    }


def _series_for_person(pessoa_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_series_longitudinais_metricas", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "select": (
            "metrica_id,metrica_codigo,nome_canonico,dominio,amostras,primeira_medicao_em,"
            "ultima_medicao_em,unidades_distintas,protocolos_distintos,versoes_metricas_distintas,"
            "completude_media,confiabilidade_media,primeiro_valor,ultimo_valor,unidade_atual,"
            "protocolo_atual_id,estado_comparabilidade,delta_absoluto,delta_percentual"
        ),
        "order": "dominio.asc,metrica_codigo.asc",
    }))


def _fact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrica_id": row.get("metrica_id"),
        "metrica_codigo": row.get("metrica_codigo"),
        "nome": row.get("nome_canonico"),
        "dominio": row.get("dominio"),
        "amostras": row.get("amostras"),
        "janela": {
            "inicio": row.get("primeira_medicao_em"),
            "fim": row.get("ultima_medicao_em"),
        },
        "primeiro_valor": row.get("primeiro_valor"),
        "ultimo_valor": row.get("ultimo_valor"),
        "unidade": row.get("unidade_atual"),
        "delta_absoluto": row.get("delta_absoluto"),
        "delta_percentual": row.get("delta_percentual"),
        "qualidade": {
            "completude_media": row.get("completude_media"),
            "confiabilidade_media": row.get("confiabilidade_media"),
        },
        "estado_comparabilidade": row.get("estado_comparabilidade"),
        "interpretacao_automatica": "mudanca_observada_sem_julgamento_de_melhora_ou_piora",
    }


def _analytic_state(series: list[dict[str, Any]]) -> dict[str, Any]:
    if not series:
        return {
            "estado": "dados_insuficientes",
            "pronto_para_interpretacao_profissional": False,
            "motivo": "nenhuma_serie_metrica_longitudinal",
        }
    comparable = [item for item in series if item.get("estado_comparabilidade") == "comparavel"]
    if not comparable:
        return {
            "estado": "evidencia_em_formacao",
            "pronto_para_interpretacao_profissional": False,
            "motivo": "nenhuma_serie_atende_comparabilidade_estrutural",
        }
    return {
        "estado": "fatos_comparaveis_disponiveis",
        "pronto_para_interpretacao_profissional": True,
        "motivo": "existem_series_comparaveis_sem_inferencia_automatica",
    }


@router.get("/participantes/{participante_id}/analise-canonica")
def canonical_analysis(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    access = _authorize_individual_read(str(actor["pessoa_id"]), participant)

    pessoa_id = str(participant["pessoa_id"])
    series = _series_for_person(pessoa_id)
    baselines = _latest_baselines(str(participante_id))

    comparable = [item for item in series if item.get("estado_comparabilidade") == "comparavel"]
    insufficient = [item for item in series if item.get("estado_comparabilidade") == "dados_insuficientes"]
    review = [item for item in series if item.get("estado_comparabilidade") in {"nao_comparavel", "revisao_requerida"}]

    facts = [_fact(item) for item in comparable]
    attention = [
        {
            "metrica_codigo": item.get("metrica_codigo"),
            "nome": item.get("nome_canonico"),
            "dominio": item.get("dominio"),
            "estado": item.get("estado_comparabilidade"),
            "motivos_estruturais": {
                "unidades_distintas": item.get("unidades_distintas"),
                "protocolos_distintos": item.get("protocolos_distintos"),
                "versoes_metricas_distintas": item.get("versoes_metricas_distintas"),
                "completude_media": item.get("completude_media"),
                "confiabilidade_media": item.get("confiabilidade_media"),
            },
            "acao": "preservar_evidencia_e_revisar_comparabilidade_antes_de_interpretar",
        }
        for item in review
    ]

    return {
        "modelo": "AGP-Canonical-Analytic-v1",
        "versao_motor": ENGINE_VERSION,
        "principio": "evidencia_comparavel_antes_de_interpretacao_sem_score_global",
        "participante_id": str(participante_id),
        "pessoa_id": pessoa_id,
        "acesso": access,
        "estado_analitico": _analytic_state(series),
        "contexto_crescimento_maturacao": _maturation_context(baselines),
        "fatos_comparaveis": facts,
        "series_com_dados_insuficientes": [
            {
                "metrica_codigo": item.get("metrica_codigo"),
                "nome": item.get("nome_canonico"),
                "dominio": item.get("dominio"),
                "amostras": item.get("amostras"),
            }
            for item in insufficient
        ],
        "series_requerendo_revisao": attention,
        "resumo": {
            "metricas_total": len(series),
            "metricas_comparaveis": len(comparable),
            "metricas_dados_insuficientes": len(insufficient),
            "metricas_requerendo_revisao": len(review),
        },
        "limites": [
            "Não existe score global canônico nesta análise.",
            "Delta não significa melhora ou piora sem regra científica específica da métrica.",
            "Proximidade temporal não estabelece causalidade.",
            "Mudança de maturação, categoria ou contexto esportivo deve ser considerada na interpretação.",
            "Conclusões clínicas ou reguladas exigem profissional competente e credencial aplicável.",
        ],
    }
