from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request

router = APIRouter(prefix="/api/v1", tags=["canonical-longitudinal-intelligence"])


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


def _target_participant(participante_id: UUID) -> dict[str, Any]:
    participant = _first(
        _request(
            "GET",
            "/rest/v1/agp_participantes_projeto",
            params={
                "id": f"eq.{participante_id}",
                "ativo": "eq.true",
                "select": "id,pessoa_id,projeto_id,funcao_no_projeto,funcao_canonica_codigo,ativo",
                "limit": "1",
            },
        )
    )
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante ativo não encontrado")
    if participant.get("funcao_canonica_codigo") not in (None, "athlete") and participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Participante não representa atleta")
    return participant


def _authorize_individual_read(actor_pessoa_id: str, participant: dict[str, Any]) -> dict[str, Any]:
    if actor_pessoa_id == str(participant["pessoa_id"]):
        return {"modo": "proprio", "capacidades": ["own.read"]}

    project_id = participant.get("projeto_id")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contexto de projeto ausente")

    contexts = _rows(
        _request(
            "GET",
            "/rest/v1/agp_contextos_identidade_efetivos",
            params={
                "pessoa_id": f"eq.{actor_pessoa_id}",
                "projeto_id": f"eq.{project_id}",
                "status": "eq.ativo",
                "select": "papel_codigo,familia,projeto_id,capacidades,competencias",
            },
        )
    )

    capabilities = {
        item.get("codigo")
        for row in contexts
        for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }
    allowed = {
        "analysis.performance",
        "evidence.review_technical",
        "decision.technical",
        "training.plan",
    }
    granted = sorted(capabilities.intersection(allowed))
    if not granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Papel atual não possui escopo para leitura longitudinal individual deste atleta",
        )
    return {"modo": "profissional_projeto", "capacidades": granted}


def _state_message(state: dict[str, Any]) -> dict[str, str]:
    current = state.get("estado")
    if current == "sem_evidencia_longitudinal":
        return {
            "estado": current,
            "significado": "Ainda não existem observações métricas suficientes para análise longitudinal.",
            "proxima_acao": "Manter coleta operacional rastreável; não emitir tendência.",
        }
    if current == "evidencia_em_formacao":
        return {
            "estado": current,
            "significado": "Há evidência registrada, mas ainda sem série comparável suficiente.",
            "proxima_acao": "Aumentar continuidade e preservar protocolo, unidade e versão de medição.",
        }
    return {
        "estado": current or "dados_insuficientes",
        "significado": "Existem séries que podem ser observadas longitudinalmente sem inferir causalidade.",
        "proxima_acao": "Interpretar mudanças apenas no contexto esportivo, do ciclo e da qualidade da evidência.",
    }


@router.get("/participantes/{participante_id}/inteligencia-longitudinal")
def longitudinal_intelligence(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
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
    ) or {
        "pessoa_id": pessoa_id,
        "ciclos_total": 0,
        "marcos": 0,
        "metricas_observadas": 0,
        "metricas_comparaveis": 0,
        "metricas_com_dados_insuficientes": 0,
        "metricas_requerendo_revisao": 0,
        "estado": "sem_evidencia_longitudinal",
    }

    series = _rows(
        _request(
            "GET",
            "/rest/v1/agp_series_longitudinais_metricas",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "select": "metrica_id,metrica_codigo,nome_canonico,dominio,amostras,primeira_medicao_em,ultima_medicao_em,completude_media,confiabilidade_media,primeiro_valor,ultimo_valor,unidade_atual,estado_comparabilidade,delta_absoluto,delta_percentual",
                "order": "dominio.asc,metrica_codigo.asc",
            },
        )
    )

    cycles = _rows(
        _request(
            "GET",
            "/rest/v1/agp_ciclos_longitudinais",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "select": "id,ciclo_pai_id,nivel,codigo,nome,objetivo,inicio,fim,status,versao",
                "order": "inicio.desc",
                "limit": "100",
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
                "limit": "50",
            },
        )
    )

    comparable = [row for row in series if row.get("estado_comparabilidade") == "comparavel"]
    review = [row for row in series if row.get("estado_comparabilidade") in ("nao_comparavel", "revisao_requerida")]
    insufficient = [row for row in series if row.get("estado_comparabilidade") == "dados_insuficientes"]

    factual_changes = [
        {
            "metrica_codigo": row.get("metrica_codigo"),
            "nome": row.get("nome_canonico"),
            "dominio": row.get("dominio"),
            "amostras": row.get("amostras"),
            "primeiro_valor": row.get("primeiro_valor"),
            "ultimo_valor": row.get("ultimo_valor"),
            "unidade": row.get("unidade_atual"),
            "delta_absoluto": row.get("delta_absoluto"),
            "delta_percentual": row.get("delta_percentual"),
            "primeira_medicao_em": row.get("primeira_medicao_em"),
            "ultima_medicao_em": row.get("ultima_medicao_em"),
            "interpretacao": "mudanca_observada_sem_julgamento_de_melhora_ou_piora",
        }
        for row in comparable
        if row.get("delta_absoluto") is not None
    ]

    return {
        "modelo": "AGP-Longitudinal-Individual-v1",
        "principio": "fato_comparavel_antes_de_inferencia",
        "acesso": access,
        "participante_id": str(participante_id),
        "pessoa_id": pessoa_id,
        "estado_longitudinal": state,
        "devolucao_operacional": _state_message(state),
        "mudancas_observadas": factual_changes,
        "series_comparaveis": comparable,
        "series_requerendo_revisao": review,
        "series_com_dados_insuficientes": insufficient,
        "ciclos": cycles,
        "marcos": milestones,
        "limites": [
            "Delta não significa melhora ou piora sem regra científica específica da métrica.",
            "Associação temporal não estabelece causalidade.",
            "Mudança de protocolo, unidade ou versão exige revisão antes da comparação.",
            "Conclusões clínicas ou reguladas dependem de profissional competente.",
        ],
    }
