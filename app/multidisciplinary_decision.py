from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["multidisciplinary-decision"])

DOMAINS = {
    "fisico", "fisiologico", "biologico", "tecnico", "mental", "psicologico",
    "medico", "recuperacao", "contextual", "crescimento", "maturacao", "nutricional",
}


class ProfessionalAssessmentInput(BaseModel):
    dominio: str
    papel_profissional: str = Field(min_length=2, max_length=120)
    instrumento_referencia: str | None = Field(default=None, max_length=240)
    metricas: dict[str, Any] = Field(default_factory=dict)
    achados: list[Any] = Field(default_factory=list)
    restricoes: list[Any] = Field(default_factory=list)
    recomendacoes: list[Any] = Field(default_factory=list)
    confianca: float | None = Field(default=None, ge=0, le=100)
    validade_ate: datetime | None = None


class InterventionInput(BaseModel):
    dominio: str
    papel_responsavel: str = Field(min_length=2, max_length=120)
    descricao: str = Field(min_length=10, max_length=5000)
    justificativa: str = Field(min_length=10, max_length=5000)
    evidencia_origem: list[dict[str, Any]] = Field(min_items=1)
    resultado_esperado: dict[str, Any] = Field(default_factory=dict)
    fim_previsto: datetime | None = None
    status: Literal["proposta", "ativa"] = "proposta"


class InterventionResponseInput(BaseModel):
    papel_avaliador: str = Field(min_length=2, max_length=120)
    janela_inicio: datetime | None = None
    janela_fim: datetime | None = None
    metricas_antes: dict[str, Any] = Field(default_factory=dict)
    metricas_depois: dict[str, Any] = Field(default_factory=dict)
    classificacao_resposta: Literal["melhora", "neutra", "piora", "inconclusiva"]
    confianca: float | None = Field(default=None, ge=0, le=100)
    conclusao: str = Field(min_length=10, max_length=5000)
    recomendacao_proximo_ciclo: str | None = Field(default=None, max_length=5000)


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _resolve_participant(participante_id: UUID) -> tuple[dict[str, Any], dict[str, Any], UUID]:
    participant = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "id": f"eq.{participante_id}",
        "select": "id,pessoa_id,projeto_id,funcao_no_projeto,status_onboarding,ativo,tecnico_responsavel_pessoa_id",
        "limit": "1",
    }))
    if not participant:
        raise HTTPException(status_code=404, detail="Participante não encontrado")
    if participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=422, detail="O participante selecionado não é atleta")

    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{participant['pessoa_id']}",
        "status": "eq.ativo",
        "select": "id,legacy_perfil_atleta_id,modalidade,prova_posicao,categoria,nivel",
        "limit": "1",
    })) or {}
    athlete_id = profile.get("legacy_perfil_atleta_id")
    if not athlete_id:
        eligibility = _request("POST", "/rest/v1/rpc/agp_elegibilidade_operacional", payload={
            "p_participante_id": str(participante_id)
        })
        if isinstance(eligibility, dict):
            athlete_id = eligibility.get("atleta_id")
    if not athlete_id:
        raise HTTPException(status_code=422, detail="Atleta canônico não resolvido para este participante")
    return participant, profile, UUID(str(athlete_id))


def _numeric_delta(before: Any, after: Any) -> Any:
    if isinstance(before, bool) or isinstance(after, bool):
        return None
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return round(float(after) - float(before), 4)
    if isinstance(before, dict) and isinstance(after, dict):
        output: dict[str, Any] = {}
        for key in sorted(set(before) & set(after)):
            delta = _numeric_delta(before[key], after[key])
            if delta is not None and delta != {}:
                output[key] = delta
        return output
    return None


def _latest_by_domain(assessments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in assessments:
        domain = item.get("dominio")
        if domain and domain not in latest and item.get("status") == "validada":
            latest[domain] = item
    return latest


def _synthesis(
    assessments: list[dict[str, Any]],
    results: list[dict[str, Any]],
    interventions: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    collections: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = _latest_by_domain(assessments)
    covered = sorted(latest.keys())
    expected = sorted(DOMAINS)
    missing = [item for item in expected if item not in latest]

    restrictions: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    for domain, item in latest.items():
        for restriction in item.get("restricoes") or []:
            restrictions.append({"dominio": domain, "origem": item.get("papel_profissional"), "conteudo": restriction})
        for recommendation in item.get("recomendacoes") or []:
            recommendations.append({"dominio": domain, "origem": item.get("papel_profissional"), "conteudo": recommendation})

    validated_results = [r for r in results if r.get("status") == "validado"]
    active_interventions = [i for i in interventions if i.get("status") in {"proposta", "ativa", "em_andamento"}]
    latest_response = responses[0] if responses else None

    if restrictions:
        state = "restricao_profissional_presente"
        next_action = "Revisar as restrições profissionais antes de alterar carga, conteúdo ou disponibilidade competitiva."
    elif active_interventions and not latest_response:
        state = "intervencao_sem_resposta_mensurada"
        next_action = "Mensurar a resposta da intervenção com a mesma métrica ou referência usada na decisão inicial."
    elif latest_response and latest_response.get("classificacao_resposta") == "piora":
        state = "resposta_desfavoravel"
        next_action = "Reavaliar a intervenção e o contexto multidisciplinar antes de mantê-la."
    elif latest_response and latest_response.get("classificacao_resposta") == "melhora":
        state = "resposta_favoravel"
        next_action = "Confirmar sustentação do efeito e decidir continuidade, progressão ou retirada da intervenção."
    elif validated_results:
        state = "resultado_validado_sem_intervencao"
        next_action = "Converter o resultado validado em ação rastreável quando houver justificativa profissional."
    elif assessments:
        state = "avaliacoes_em_consolidacao"
        next_action = "Cruzar as avaliações profissionais com treino, recuperação e evidências longitudinais antes da intervenção."
    else:
        state = "sem_avaliacao_multidisciplinar"
        next_action = "Registrar avaliações profissionais reais conforme a necessidade do atleta; não preencher domínios por obrigação."

    return {
        "estado": state,
        "proxima_acao": next_action,
        "dominios_com_avaliacao": covered,
        "dominios_sem_avaliacao": missing,
        "cobertura_multidisciplinar_percentual": round(len(covered) * 100 / len(expected), 1),
        "restricoes_ativas": restrictions,
        "recomendacoes_atuais": recommendations,
        "resultados_validados": len(validated_results),
        "intervencoes_ativas": len(active_interventions),
        "respostas_intervencao": len(responses),
        "sessoes_treinamento": len(sessions),
        "coletas": len(collections),
        "nota": "Cobertura não é meta administrativa: apenas domínios clinicamente/esportivamente pertinentes devem ser avaliados.",
    }


@router.get("/participantes/{participante_id}/ciclo-decisao")
def get_decision_cycle(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_owner(authorization)
    participant, profile, athlete_id = _resolve_participant(participante_id)

    assessments = _rows(_request("GET", "/rest/v1/agp_avaliacoes_profissionais", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "data_avaliacao.desc", "limit": "100"
    }))
    results = _rows(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
        "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "created_at.desc", "limit": "30"
    }))
    interventions = _rows(_request("GET", "/rest/v1/agp_intervencoes", params={
        "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "created_at.desc", "limit": "50"
    }))
    responses = _rows(_request("GET", "/rest/v1/agp_respostas_intervencao", params={
        "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "data_avaliacao.desc", "limit": "50"
    }))
    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_treinamento", params={
        "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "data_hora_inicio.desc", "limit": "50"
    }))
    collections = _rows(_request("GET", "/rest/v1/agp_coletas", params={
        "participante_id": f"eq.{participante_id}", "select": "id,status,data_hora_coleta,instrumento_id,protocolo_id,dados,confiabilidade,completude", "order": "data_hora_coleta.desc", "limit": "100"
    }))
    validations = _rows(_request("GET", "/rest/v1/agp_validacoes_profissionais", params={
        "resultado_id": f"in.({','.join(str(r['id']) for r in results)})" if results else "eq.00000000-0000-0000-0000-000000000000",
        "select": "*", "order": "created_at.desc", "limit": "100"
    }))
    documents = _rows(_request("GET", "/rest/v1/agp_documentos_profissionais", params={
        "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "data_documento.desc", "limit": "50"
    }))

    return {
        "versao_nucleo": "agp-multidisciplinary-decision-v1",
        "participante": participant,
        "perfil_esportivo": profile,
        "atleta_id": str(athlete_id),
        "sintese": _synthesis(assessments, results, interventions, responses, sessions, collections),
        "avaliacoes_profissionais": assessments,
        "resultados_analiticos": results,
        "validacoes_profissionais": validations,
        "intervencoes": interventions,
        "respostas_intervencao": responses,
        "documentos_profissionais": documents,
        "sessoes_recentes": sessions[:10],
        "coletas_recentes": collections[:10],
    }


@router.post("/participantes/{participante_id}/avaliacoes-profissionais", status_code=status.HTTP_201_CREATED)
def create_professional_assessment(
    participante_id: UUID,
    payload: ProfessionalAssessmentInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    participant, _profile, athlete_id = _resolve_participant(participante_id)
    if payload.dominio not in DOMAINS:
        raise HTTPException(status_code=422, detail="Domínio profissional inválido")
    return _single_row(_request("POST", "/rest/v1/agp_avaliacoes_profissionais", payload={
        "participante_id": str(participante_id),
        "atleta_id": str(athlete_id),
        "projeto_id": participant["projeto_id"],
        "dominio": payload.dominio,
        "papel_profissional": payload.papel_profissional,
        "profissional_auth_id": str(owner_id),
        "instrumento_referencia": payload.instrumento_referencia,
        "metricas": payload.metricas,
        "achados": payload.achados,
        "restricoes": payload.restricoes,
        "recomendacoes": payload.recomendacoes,
        "confianca": payload.confianca,
        "validade_ate": payload.validade_ate.isoformat() if payload.validade_ate else None,
        "status": "validada",
    }), "avaliação profissional")


@router.post("/participantes/{participante_id}/intervencoes", status_code=status.HTTP_201_CREATED)
def create_intervention(
    participante_id: UUID,
    payload: InterventionInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    participant, _profile, athlete_id = _resolve_participant(participante_id)
    if payload.dominio not in DOMAINS:
        raise HTTPException(status_code=422, detail="Domínio da intervenção inválido")
    return _single_row(_request("POST", "/rest/v1/agp_intervencoes", payload={
        "atleta_id": str(athlete_id),
        "projeto_id": participant["projeto_id"],
        "dominio": payload.dominio,
        "responsavel_auth_id": str(owner_id),
        "papel_responsavel": payload.papel_responsavel,
        "descricao": payload.descricao,
        "justificativa": payload.justificativa,
        "evidencia_origem": payload.evidencia_origem,
        "resultado_esperado": payload.resultado_esperado,
        "inicio": datetime.now(timezone.utc).isoformat(),
        "fim_previsto": payload.fim_previsto.isoformat() if payload.fim_previsto else None,
        "status": payload.status,
    }), "intervenção")


@router.post("/intervencoes/{intervencao_id}/respostas", status_code=status.HTTP_201_CREATED)
def create_intervention_response(
    intervencao_id: UUID,
    payload: InterventionResponseInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    intervention = _first(_request("GET", "/rest/v1/agp_intervencoes", params={
        "id": f"eq.{intervencao_id}", "select": "*", "limit": "1"
    }))
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervenção não encontrada")

    participant = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "projeto_id": f"eq.{intervention['projeto_id']}",
        "funcao_no_projeto": "eq.atleta",
        "select": "id,pessoa_id,projeto_id",
    }))
    if not participant:
        raise HTTPException(status_code=422, detail="Participante canônico da intervenção não encontrado")

    variations = _numeric_delta(payload.metricas_antes, payload.metricas_depois) or {}
    response = _single_row(_request("POST", "/rest/v1/agp_respostas_intervencao", payload={
        "intervencao_id": str(intervencao_id),
        "participante_id": participant["id"],
        "atleta_id": intervention["atleta_id"],
        "projeto_id": intervention["projeto_id"],
        "avaliado_por_auth_id": str(owner_id),
        "papel_avaliador": payload.papel_avaliador,
        "janela_inicio": payload.janela_inicio.isoformat() if payload.janela_inicio else None,
        "janela_fim": payload.janela_fim.isoformat() if payload.janela_fim else None,
        "metricas_antes": payload.metricas_antes,
        "metricas_depois": payload.metricas_depois,
        "variacoes": variations,
        "classificacao_resposta": payload.classificacao_resposta,
        "confianca": payload.confianca,
        "conclusao": payload.conclusao,
        "recomendacao_proximo_ciclo": payload.recomendacao_proximo_ciclo,
    }), "resposta da intervenção")

    new_status = "concluida" if payload.classificacao_resposta in {"melhora", "neutra", "piora"} else "em_andamento"
    try:
        _request("PATCH", "/rest/v1/agp_intervencoes", params={"id": f"eq.{intervencao_id}"}, payload={"status": new_status})
    except Exception:
        pass
    return response
