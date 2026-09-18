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
        return {"status": "sem_evidencia", "amostras": 0, "ultimo": None, "baseline": {}, "mudancas_nominais": []}

    latest = valid[-1]
    data = latest.get("dados") or {}
    fields = ["sono_horas", "qualidade_sono", "fadiga", "dor", "estresse", "humor", "rpe_ultima_sessao"]
    baseline: dict[str, Any] = {}
    nominal_changes: list[dict[str, Any]] = []

    for field in fields:
        prior_values = [_num(item.get("dados", {}).get(field)) for item in valid[-8:-1]]
        prior_values = [value for value in prior_values if value is not None]
        latest_value = _num(data.get(field))
        personal_mean = round(mean(prior_values), 2) if prior_values else None
        delta = round(latest_value - personal_mean, 2) if latest_value is not None and personal_mean is not None else None
        baseline[field] = {
            "media_pessoal_anterior": personal_mean,
            "ultimo": latest_value,
            "amostras_anteriores": len(prior_values),
            "delta_nominal": delta,
        }
        if delta is not None:
            nominal_changes.append({
                "campo": field,
                "ultimo": latest_value,
                "media_pessoal_anterior": personal_mean,
                "delta_nominal": delta,
                "significado": "mudanca_nominal_sem_julgamento_automatico",
            })

    return {
        "status": "baseline_em_formacao" if len(valid) < 3 else "evidencia_contextual_disponivel",
        "amostras": len(valid),
        "ultimo": latest,
        "baseline": baseline,
        "mudancas_nominais": nominal_changes,
        "sinais": [],
        "principio": "sem_limites_universais_nao_validados; interpretar_com_contexto_e_competencia_profissional",
    }


def _coverage(collections: list[dict[str, Any]], sessions: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in collections if c.get("status") == "validada"]
    days = {str(c.get("data_hora_coleta") or "")[:10] for c in valid if c.get("data_hora_coleta")}
    completeness = mean([float(c.get("completude") or 0) for c in valid]) if valid else 0.0
    reliability_values = [float(c.get("confiabilidade")) for c in valid if c.get("confiabilidade") is not None]
    reliability = mean(reliability_values) if reliability_values else None
    coverage = min(100.0, len(days) * 100.0 / 14.0)
    validated_result = any(r.get("status") == "validado" for r in results)
    return {
        "janela_dias": 14,
        "dias_com_evidencia_validada": len(days),
        "cobertura_percentual": round(coverage, 1),
        "completude_media": round(completeness, 1),
        "confiabilidade_media_documentada": round(reliability, 1) if reliability is not None else None,
        "sessoes_treino_disponiveis": len(sessions),
        "resultado_profissional_validado": validated_result,
        "estado_cobertura": (
            "sem_evidencia" if not valid
            else "inicial" if len(days) < 3
            else "em_formacao" if len(days) < 7
            else "continua"
        ),
        "nota": "Cobertura operacional; não é score de performance, risco ou prontidão.",
    }


def _return(readiness: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    if readiness["amostras"] == 0:
        return {
            "estado": "aguardando_evidencia",
            "mensagem": "Ainda não há evidência suficiente para uma leitura longitudinal individual.",
            "acao_prioritaria": "Realizar a primeira coleta de prontidão e registrar a execução das sessões.",
        }
    if readiness["amostras"] < 3:
        return {
            "estado": "baseline_em_formacao",
            "mensagem": "A referência pessoal começou a ser formada, mas ainda não há base suficiente para tendência.",
            "acao_prioritaria": "Manter coletas consistentes e relacioná-las aos treinos executados.",
        }
    return {
        "estado": "evidencia_contextual_disponivel",
        "mensagem": "Há histórico autodeclarado suficiente para comparação nominal com a própria linha de base, sem diagnóstico ou julgamento automático.",
        "acao_prioritaria": "Cruzar prontidão, treino executado, avaliações e contexto antes de qualquer decisão profissional.",
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
    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "id,status,tipo_sessao,objetivo,inicio_planejado,inicio_real,fim_real,contexto_esportivo,created_at",
        "order": "inicio_planejado.desc",
        "limit": "30",
    }))
    results: list[dict[str, Any]] = []
    interventions = _rows(_request("GET", "/rest/v1/agp_intervencoes_canonicas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "*",
        "order": "created_at.desc",
        "limit": "10",
    }))
    if athlete_id:
        results = _rows(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
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
