from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant

router = APIRouter(prefix="/api/v1", tags=["canonical-self-report"])

READINESS_CODE = "AGP-READINESS-DAILY-Q"

READINESS_METRICS = {
    "sono_horas": ("AGP_READINESS_SLEEP_HOURS", "h"),
    "qualidade_sono": ("AGP_READINESS_SLEEP_QUALITY", "1-5"),
    "fadiga": ("AGP_READINESS_FATIGUE", "1-5"),
    "dor": ("AGP_READINESS_PAIN", "0-10"),
    "estresse": ("AGP_READINESS_STRESS", "1-5"),
    "humor": ("AGP_READINESS_MOOD", "1-5"),
    "rpe_ultima_sessao": ("AGP_READINESS_LAST_SESSION_RPE", "0-10"),
}



def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _contexts(pessoa_id: str, projeto_id: str) -> list[dict[str, Any]]:
    return _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "projeto_id": f"eq.{projeto_id}",
        "status": "eq.ativo",
        "select": "papel_codigo,capacidades",
    }))


def _caps(contexts: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("codigo")
        for row in contexts
        for item in (row.get("capacidades") or [])
        if isinstance(item, dict) and item.get("codigo")
    }


def _authorize_self_report(actor_pessoa_id: str, participant: dict[str, Any]) -> None:
    if actor_pessoa_id != str(participant["pessoa_id"]):
        raise HTTPException(status_code=403, detail="Autorreporte diário só pode ser respondido pela própria pessoa")
    capabilities = _caps(_contexts(actor_pessoa_id, str(participant.get("projeto_id") or "")))
    if "self_report.write" not in capabilities:
        raise HTTPException(status_code=403, detail="Papel atual não possui capacidade de autorreporte")


def _instrument_for_project(project_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    instrument = _first(_request("GET", "/rest/v1/agp_instrumentos", params={
        "codigo": f"eq.{READINESS_CODE}",
        "ativo": "eq.true",
        "status_catalogo": "eq.aprovado",
        "select": "id,codigo,nome,versao,tipo,respondente,periodicidade,schema_campos,regra_completude,protocolo_id",
        "limit": "1",
    }))
    if not instrument:
        raise HTTPException(status_code=503, detail="Instrumento diário canônico indisponível")
    activation = _first(_request("GET", "/rest/v1/agp_ativacoes_instrumentos", params={
        "instrumento_id": f"eq.{instrument['id']}",
        "projeto_id": f"eq.{project_id}",
        "ativo": "eq.true",
        "select": "id,instrumento_id,projeto_id,modalidade,categoria,versao_configuracao,configuracao,data_inicio,data_fim,aprovado_em",
        "order": "data_inicio.desc",
        "limit": "1",
    }))
    if not activation or not activation.get("aprovado_em"):
        raise HTTPException(status_code=503, detail="Questionário diário não está ativado e aprovado para este projeto")
    return instrument, activation


class DailyReadinessReport(BaseModel):
    sono_horas: float = Field(ge=0, le=24)
    qualidade_sono: int = Field(ge=1, le=5)
    fadiga: int = Field(ge=1, le=5)
    dor: int = Field(ge=0, le=10)
    estresse: int = Field(ge=1, le=5)
    humor: int = Field(ge=1, le=5)
    rpe_ultima_sessao: int = Field(ge=0, le=10)
    observacao: str | None = Field(default=None, max_length=2000)
    ciclo_id: UUID | None = None


@router.get("/participantes/{participante_id}/autorreporte-diario")
def get_daily_self_report(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    _authorize_self_report(str(actor["pessoa_id"]), participant)
    instrument, activation = _instrument_for_project(str(participant["projeto_id"]))
    history = _rows(_request("GET", "/rest/v1/agp_coletas_canonicas", params={
        "participante_id": f"eq.{participante_id}",
        "instrumento_codigo": f"eq.{READINESS_CODE}",
        "select": "id,data_hora_coleta,status,completude,natureza_validacao,bloqueado_para_edicao,dados,versao_instrumento",
        "order": "data_hora_coleta.desc",
        "limit": "14",
    }))
    return {
        "modelo": "AGP-Athlete-Self-Report-v1",
        "instrumento": instrument,
        "ativacao": activation,
        "historico_recente": history,
        "principio": "autoria_do_atleta_evidencia_nao_diagnostico",
        "validacao_semantica": "autoria_estrutura_nao_equivale_a_validacao_clinica",
    }


@router.post("/participantes/{participante_id}/autorreporte-diario", status_code=status.HTTP_201_CREATED)
def submit_daily_self_report(
    participante_id: UUID,
    payload: DailyReadinessReport,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    _authorize_self_report(str(actor["pessoa_id"]), participant)
    instrument, activation = _instrument_for_project(str(participant["projeto_id"]))
    now = datetime.now(timezone.utc).isoformat()
    data = payload.dict(exclude={"ciclo_id"})
    if data.get("observacao") is None:
        data.pop("observacao", None)
    row = {
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "instrumento_id": instrument["id"],
        "ativacao_instrumento_id": activation["id"],
        "protocolo_id": instrument.get("protocolo_id"),
        "coletado_por_auth_id": str(user["id"]),
        "papel_coletor": "athlete",
        "data_hora_coleta": now,
        "origem": "athlete_self_report",
        "status": "validada",
        "dados": data,
        "versao_schema": "1.0.0",
        "ciclo_referencia": str(payload.ciclo_id) if payload.ciclo_id else None,
        "iniciado_em": now,
        "submetido_em": now,
        "natureza_validacao": "autoria_estrutura",
        "validado_por_auth_id": str(user["id"]),
        "validado_em": now,
    }
    created = _first(_request("POST", "/rest/v1/agp_coletas", payload=row))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar autorreporte diário")

    metric_codes = [code for code, _unit in READINESS_METRICS.values()]
    metrics = _rows(_request("GET", "/rest/v1/agp_metricas_esportivas_canonicas", params={
        "codigo": f"in.({','.join(metric_codes)})",
        "ativo": "eq.true",
        "select": "id,codigo",
    }))
    metric_map = {item.get("codigo"): item.get("id") for item in metrics if item.get("codigo") and item.get("id")}

    for order, (field, (code, unit)) in enumerate(READINESS_METRICS.items()):
        metric_id = metric_map.get(code)
        value = data.get(field)
        if not metric_id or value is None:
            continue
        _request("POST", "/rest/v1/agp_coleta_metricas", payload={
            "coleta_id": created["id"],
            "metrica_id": metric_id,
            "ordem": order,
            "valor_numerico": value,
            "unidade": unit,
            "contexto_medicao": {
                "origem": "athlete_self_report",
                "instrumento_codigo": READINESS_CODE,
                "versao_instrumento": instrument.get("versao"),
                "versao_schema": "1.0.0",
                "campo": field,
                "scale_version": "1.0.0",
            },
            "qualidade": {
                "natureza": "autodeclarado",
                "validacao": "autoria_estrutura",
                "diagnostico": False,
            },
            "measured_at": now,
        })

    if payload.ciclo_id:
        _request("POST", "/rest/v1/agp_ciclo_coletas", payload={
            "ciclo_id": str(payload.ciclo_id),
            "coleta_id": created["id"],
        })

    return {
        "coleta": created,
        "metricas_materializadas": [field for field in READINESS_METRICS if data.get(field) is not None],
        "significado": "relato_autodeclarado_do_atleta",
        "nao_significa": ["diagnostico", "causalidade", "decisao_clinica_automatica"],
    }
