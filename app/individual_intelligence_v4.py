from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1", tags=["individual-intelligence-v4"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _participant(participante_id: UUID) -> dict[str, Any]:
    row = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "id": f"eq.{participante_id}",
        "select": "id,pessoa_id,projeto_id,funcao_no_projeto,tecnico_responsavel_pessoa_id,status_onboarding,ativo,data_inicio",
        "limit": "1",
    }))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    if row.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Participante não é atleta")
    return row


def _athlete_id(participant: dict[str, Any]) -> str | None:
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{participant['pessoa_id']}",
        "status": "eq.ativo",
        "select": "legacy_perfil_atleta_id",
        "limit": "1",
    }))
    if profile and profile.get("legacy_perfil_atleta_id"):
        return str(profile["legacy_perfil_atleta_id"])

    baseline = _first(_request("GET", "/rest/v1/agp_linhas_base_atleta", params={
        "participante_id": f"eq.{participant['id']}",
        "status": "eq.vigente",
        "select": "atleta_id",
        "order": "data_referencia.desc",
        "limit": "1",
    }))
    return str(baseline["atleta_id"]) if baseline and baseline.get("atleta_id") else None


def _readiness(collections: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in collections if c.get("status") == "validada" and isinstance(c.get("dados"), dict)]
    valid.sort(key=lambda c: str(c.get("data_hora_coleta") or c.get("created_at") or ""))
    if not valid:
        return {"status": "sem_evidencia", "amostras": 0, "ultimo": None, "sinais": []}

    latest = valid[-1]
    data = latest.get("dados") or {}
    signals: list[dict[str, str]] = []
    sleep = _num(data.get("sono_horas"))
    fatigue = _num(data.get("fadiga"))
    pain = _num(data.get("dor"))
    stress = _num(data.get("estresse"))
    mood = _num(data.get("humor"))
    rpe = _num(data.get("rpe_ultima_sessao"))

    if pain is not None and pain >= 7:
        signals.append({"nivel": "alto", "dominio": "dor", "mensagem": "Dor autorreferida elevada; requer revisão profissional antes de intensificar carga."})
    elif pain is not None and pain >= 4:
        signals.append({"nivel": "atencao", "dominio": "dor", "mensagem": "Dor acima da faixa baixa; acompanhar evolução e contexto."})
    if sleep is not None and sleep < 6:
        signals.append({"nivel": "atencao", "dominio": "recuperacao", "mensagem": "Sono abaixo de 6 horas no registro mais recente."})
    if fatigue is not None and fatigue >= 4:
        signals.append({"nivel": "atencao", "dominio": "recuperacao", "mensagem": "Fadiga percebida elevada."})
    if stress is not None and stress >= 4:
        signals.append({"nivel": "atencao", "dominio": "contextual", "mensagem": "Estresse percebido elevado."})
    if mood is not None and mood <= 2:
        signals.append({"nivel": "atencao", "dominio": "mental", "mensagem": "Humor autorreferido baixo; interpretar em conjunto com contexto e equipe."})
    if rpe is not None and fatigue is not None and rpe >= 8 and fatigue >= 4:
        signals.append({"nivel": "atencao", "dominio": "carga_recuperacao", "mensagem": "Esforço alto coexistindo com fadiga elevada."})

    fields = ["sono_horas", "qualidade_sono", "fadiga", "dor", "estresse", "humor", "rpe_ultima_sessao"]
    baseline: dict[str, Any] = {}
    for field in fields:
        values = [_num(c.get("dados", {}).get(field)) for c in valid[-7:]]
        values = [v for v in values if v is not None]
        baseline[field] = {
            "media_pessoal": round(mean(values), 2) if values else None,
            "ultimo": _num(data.get(field)),
            "amostras": len(values),
        }

    return {
        "status": "baseline_em_formacao" if len(valid) < 3 else "longitudinal",
        "amostras": len(valid),
        "ultimo": latest,
        "baseline": baseline,
        "sinais": signals,
    }


def _coverage(collections: list[dict[str, Any]], sessions: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in collections if c.get("status") == "validada"]
    days = {str(c.get("data_hora_coleta") or "")[:10] for c in valid if c.get("data_hora_coleta")}
    completeness = mean([float(c.get("completude") or 0) for c in valid]) if valid else 0.0
    reliability_values = [float(c.get("confiabilidade")) for c in valid if c.get("confiabilidade") is not None]
    reliability = mean(reliability_values) if reliability_values else (100.0 if valid and completeness >= 100 else 0.0)
    coverage = min(100.0, len(days) * 100.0 / 14.0)
    validated_result = any(r.get("status") == "validado" for r in results)
    confidence = min(100.0, 0.45 * coverage + 0.30 * completeness + 0.15 * reliability + (5 if sessions else 0) + (5 if validated_result else 0))
    label = "alta" if confidence >= 75 else "moderada" if confidence >= 45 else "baixa"
    return {
        "janela_dias": 14,
        "dias_com_evidencia_validada": len(days),
        "cobertura_percentual": round(coverage, 1),
        "completude_media": round(completeness, 1),
        "confiabilidade_media": round(reliability, 1),
        "sessoes_treino_disponiveis": len(sessions),
        "resultado_profissional_validado": validated_result,
        "confianca_geral": round(confidence, 1),
        "classificacao_confianca": label,
    }


def _return(readiness: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    if readiness["amostras"] == 0:
        return {
            "estado": "aguardando_evidencia",
            "mensagem": "Ainda não há evidência validada suficiente para interpretar o estado individual do atleta.",
            "acao_prioritaria": "Realizar e validar a primeira coleta de prontidão diária.",
        }
    if readiness["amostras"] < 3:
        return {
            "estado": "baseline_em_formacao",
            "mensagem": "A referência pessoal começou a ser formada, mas ainda não há amostra suficiente para tendência.",
            "acao_prioritaria": "Manter coletas consistentes até alcançar pelo menos três registros válidos.",
        }
    high = [s for s in readiness["sinais"] if s.get("nivel") == "alto"]
    if high:
        return {
            "estado": "revisao_profissional_prioritaria",
            "mensagem": high[0]["mensagem"],
            "acao_prioritaria": "Revisar contexto e condição do atleta antes de intensificar a próxima carga.",
        }
    if readiness["sinais"]:
        return {
            "estado": "atencao_contextual",
            "mensagem": "Existem sinais que merecem acompanhamento conjunto entre atleta e equipe.",
            "acao_prioritaria": "Cruzar prontidão, carga recente e contexto antes da próxima decisão de treino.",
        }
    if coverage["classificacao_confianca"] == "baixa":
        return {
            "estado": "sem_sinal_forte_baixa_confianca",
            "mensagem": "Não há sinal forte no registro atual, mas a cobertura ainda é insuficiente para uma conclusão robusta.",
            "acao_prioritaria": "Aumentar regularidade de prontidão e registro de sessões.",
        }
    return {
        "estado": "acompanhamento_regular",
        "mensagem": "A evidência disponível não mostra sinal operacional crítico neste momento.",
        "acao_prioritaria": "Manter monitoramento e relacionar prontidão, carga e evolução esportiva.",
    }


class TrainingSessionCreate(BaseModel):
    data_hora_inicio: datetime
    duracao_min: int = Field(ge=1, le=600)
    volume_planejado: float | None = None
    volume_executado: float | None = None
    intensidade_planejada: float | None = Field(default=None, ge=0, le=10)
    intensidade_percebida: float | None = Field(default=None, ge=0, le=10)
    carga_externa: float | None = None
    conteudo: dict[str, Any] = Field(default_factory=dict)
    intercorrencias: str | None = Field(default=None, max_length=2000)


@router.get("/participantes/{participante_id}/inteligencia-v4")
def intelligence_v4(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_owner(authorization)
    participant = _participant(participante_id)
    athlete_id = _athlete_id(participant)

    person = _first(_request("GET", "/rest/v1/agp_pessoas", params={
        "id": f"eq.{participant['pessoa_id']}", "select": "id,nome,data_nascimento,status", "limit": "1"
    })) or {}
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{participant['pessoa_id']}", "status": "eq.ativo", "select": "*", "limit": "1"
    })) or {}

    collections = _rows(_request("GET", "/rest/v1/agp_coletas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "id,participante_id,atleta_id,projeto_id,instrumento_id,data_hora_coleta,status,completude,confiabilidade,dados,origem,created_at",
        "order": "data_hora_coleta.asc", "limit": "100"
    }))
    sessions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    interventions: list[dict[str, Any]] = []
    if athlete_id:
        sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_treinamento", params={
            "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "data_hora_inicio.desc", "limit": "30"
        }))
        results = _rows(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
            "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "created_at.desc", "limit": "10"
        }))
        interventions = _rows(_request("GET", "/rest/v1/agp_intervencoes", params={
            "atleta_id": f"eq.{athlete_id}", "select": "*", "order": "created_at.desc", "limit": "10"
        }))

    readiness = _readiness(collections)
    coverage = _coverage(collections, sessions, results)
    practical = _return(readiness, coverage)

    return {
        "versao_motor": "AGP-Individual-v4.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "participante": participant,
        "pessoa": person,
        "perfil_esportivo": profile,
        "atleta_id": athlete_id,
        "prontidao": readiness,
        "cobertura": coverage,
        "devolucao": practical,
        "sessoes_recentes": sessions[:10],
        "resultados_recentes": results[:5],
        "intervencoes_recentes": interventions[:5],
    }


@router.post("/participantes/{participante_id}/sessoes", status_code=status.HTTP_201_CREATED)
def create_training_session(
    participante_id: UUID,
    payload: TrainingSessionCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    participant = _participant(participante_id)
    athlete_id = _athlete_id(participant)
    if not athlete_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Atleta legado/canônico não reconciliado para registro de sessão")

    carga_interna = None
    if payload.intensidade_percebida is not None:
        carga_interna = round(payload.duracao_min * payload.intensidade_percebida, 2)

    row = {
        "atleta_id": athlete_id,
        "tecnico_auth_id": str(operator_id),
        "data_hora_inicio": payload.data_hora_inicio.isoformat(),
        "duracao_min": payload.duracao_min,
        "volume_planejado": payload.volume_planejado,
        "volume_executado": payload.volume_executado,
        "intensidade_planejada": payload.intensidade_planejada,
        "intensidade_percebida": payload.intensidade_percebida,
        "carga_interna": carga_interna,
        "carga_externa": payload.carga_externa,
        "conteudo": payload.conteudo,
        "intercorrencias": payload.intercorrencias.strip() if payload.intercorrencias else None,
    }
    created = _first(_request("POST", "/rest/v1/agp_sessoes_treinamento", payload=row))
    if not created:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao registrar sessão")
    return created
