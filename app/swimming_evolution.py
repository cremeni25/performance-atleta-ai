from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request, _require_owner
from app.canonical_longitudinal_intelligence import (
    _actor_person,
    _authorize_individual_read,
    _target_participant,
)

router = APIRouter(prefix="/api/v1", tags=["swimming-evolution"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _month_start(year: int, month: int) -> tuple[int, int]:
    month -= 1
    if month == 0:
        return year - 1, 12
    return year, month


def _months_back(count: int = 12) -> list[tuple[int, int]]:
    now = datetime.now(timezone.utc)
    values = [(now.year, now.month)]
    y, m = now.year, now.month
    for _ in range(count - 1):
        y, m = _month_start(y, m)
        values.append((y, m))
    return list(reversed(values))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _authorize_read(
    authorization: str | None,
    participant: dict[str, Any],
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    try:
        access = _authorize_individual_read(str(actor["pessoa_id"]), participant)
        return {**access, "pessoa_id": str(actor["pessoa_id"]), "owner": False}
    except HTTPException as error:
        if error.status_code != 403:
            raise
        _require_owner(authorization)
        return {
            "modo": "governanca_somente_leitura",
            "capacidades": ["platform.govern"],
            "pessoa_id": str(actor["pessoa_id"]),
            "owner": True,
        }


@router.get("/participantes/{participante_id}/evolucao-swimming")
def swimming_evolution(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    participant = _target_participant(participante_id)
    access = _authorize_read(authorization, participant)
    pessoa_id = str(participant["pessoa_id"])

    months = _months_back(12)
    start_y, start_m = months[0]
    start_iso = datetime(start_y, start_m, 1, tzinfo=timezone.utc).isoformat()

    person = _rows(_request("GET", "/rest/v1/agp_pessoas", params={
        "id": f"eq.{pessoa_id}",
        "select": "id,nome",
        "limit": "1",
    }))
    profile = _rows(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "status": "eq.ativo",
        "select": "modalidade,categoria,nivel,status_federativo,federacao_nome,registro_federativo",
        "limit": "1",
    }))

    sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_esportivas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "id,status,tipo_sessao,objetivo,inicio_planejado,inicio_real,fim_real,contexto_esportivo,created_at",
        "order": "inicio_planejado.asc",
        "limit": "500",
    }))

    window_start = datetime(start_y, start_m, 1, tzinfo=timezone.utc)
    sessions_window = [
        item for item in sessions
        if (_parse_dt(item.get("inicio_real") or item.get("inicio_planejado") or item.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc)) >= window_start
    ]

    readiness = _rows(_request("GET", "/rest/v1/agp_coletas_canonicas", params={
        "participante_id": f"eq.{participante_id}",
        "instrumento_codigo": "eq.AGP-READINESS-DAILY-Q",
        "data_hora_coleta": f"gte.{start_iso}",
        "select": "id,data_hora_coleta,status,completude,dados",
        "order": "data_hora_coleta.asc",
        "limit": "500",
    }))

    participations_all = _rows(_request("GET", "/rest/v1/agp_participacoes_prova", params={
        "participante_id": f"eq.{participante_id}",
        "select": "id,status,tempo_oficial_ms,created_at,updated_at",
        "order": "created_at.asc",
        "limit": "200",
    }))
    participations = [
        item for item in participations_all
        if (_parse_dt(item.get("updated_at") or item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
        >= datetime(start_y, start_m, 1, tzinfo=timezone.utc)
    ]

    series = _rows(_request("GET", "/rest/v1/agp_series_longitudinais_metricas", params={
        "pessoa_id": f"eq.{pessoa_id}",
        "select": "metrica_id,metrica_codigo,nome_canonico,dominio,amostras,primeira_medicao_em,ultima_medicao_em,primeiro_valor,ultimo_valor,unidade_atual,estado_comparabilidade,delta_absoluto,delta_percentual,completude_media,confiabilidade_media",
        "order": "dominio.asc,metrica_codigo.asc",
    }))

    buckets: dict[str, dict[str, Any]] = {}
    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    for y, m in months:
        key = f"{y:04d}-{m:02d}"
        buckets[key] = {
            "mes": key,
            "rotulo": f"{month_names[m-1]} {str(y)[2:]}",
            "volume_planejado_m": 0.0,
            "volume_executado_m": 0.0,
            "sessoes": 0,
            "sessoes_concluidas": 0,
            "prontidao_registros": 0,
        }

    total_planned = 0.0
    total_executed = 0.0
    completed = 0
    for session in sessions_window:
        dt = _parse_dt(session.get("inicio_real") or session.get("inicio_planejado") or session.get("created_at"))
        if not dt:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}"
        if key not in buckets:
            continue
        ctx = session.get("contexto_esportivo") or {}
        planned = _num(ctx.get("volume_planejado")) or 0.0
        executed = _num(ctx.get("volume_executado")) or 0.0
        buckets[key]["volume_planejado_m"] += planned
        buckets[key]["volume_executado_m"] += executed
        buckets[key]["sessoes"] += 1
        total_planned += planned
        total_executed += executed
        if session.get("status") == "concluida":
            buckets[key]["sessoes_concluidas"] += 1
            completed += 1

    readiness_values: list[dict[str, Any]] = []
    for item in readiness:
        dt = _parse_dt(item.get("data_hora_coleta"))
        if dt:
            key = f"{dt.year:04d}-{dt.month:02d}"
            if key in buckets:
                buckets[key]["prontidao_registros"] += 1
        data = item.get("dados") or {}
        readiness_values.append({
            "data_hora_coleta": item.get("data_hora_coleta"),
            "sono_horas": data.get("sono_horas"),
            "qualidade_sono": data.get("qualidade_sono"),
            "fadiga": data.get("fadiga"),
            "dor": data.get("dor"),
            "estresse": data.get("estresse"),
            "humor": data.get("humor"),
            "rpe_ultima_sessao": data.get("rpe_ultima_sessao"),
        })

    comparable = [x for x in series if x.get("estado_comparabilidade") == "comparavel"]
    technical = [
        x for x in comparable
        if "tecn" in str(x.get("dominio") or "").lower()
        or "tecn" in str(x.get("nome_canonico") or "").lower()
        or "tecn" in str(x.get("metrica_codigo") or "").lower()
    ]
    technical_indicator = None
    if technical:
        candidate = sorted(technical, key=lambda x: int(x.get("amostras") or 0), reverse=True)[0]
        technical_indicator = {
            "estado": "comparavel",
            "nome": candidate.get("nome_canonico") or candidate.get("metrica_codigo"),
            "valor_atual": candidate.get("ultimo_valor"),
            "unidade": candidate.get("unidade_atual"),
            "delta_percentual": candidate.get("delta_percentual"),
            "delta_absoluto": candidate.get("delta_absoluto"),
            "amostras": candidate.get("amostras"),
            "regra": "mudanca_observada_sem_julgamento_automatico_de_melhora_ou_piora",
        }
    else:
        technical_indicator = {
            "estado": "dados_insuficientes",
            "nome": "Evolução técnica",
            "valor_atual": None,
            "unidade": None,
            "delta_percentual": None,
            "delta_absoluto": None,
            "amostras": 0,
            "regra": "nao_exibir_percentual_ilustrativo_sem_metrica_tecnica_comparavel",
        }

    recent_sessions = list(reversed(sessions_window))[:10]
    latest_readiness = list(reversed(readiness_values))[:14]

    return {
        "modelo": "AGP-Swimming-Evolution-v1",
        "participante_id": str(participante_id),
        "pessoa_id": pessoa_id,
        "atleta": {
            "nome": person[0].get("nome") if person else "Atleta",
            **(profile[0] if profile else {}),
        },
        "acesso": access,
        "janela": {
            "meses": 12,
            "inicio": start_iso,
            "fim": datetime.now(timezone.utc).isoformat(),
        },
        "resumo": {
            "volume_planejado_m": round(total_planned, 2),
            "volume_executado_m": round(total_executed, 2),
            "sessoes_total": len(sessions_window),
            "sessoes_concluidas": completed,
            "prontidao_registros": len(readiness),
            "provas_total": len(participations),
            "metricas_comparaveis": len(comparable),
        },
        "progressao_mensal": list(buckets.values()),
        "indicador_tecnico": technical_indicator,
        "series_longitudinais": series,
        "prontidao_recente": latest_readiness,
        "sessoes_recentes": recent_sessions,
        "participacoes_prova": participations,
        "principios": [
            "dados_reais_sem_indicador_ficticio",
            "evidencia_antes_de_interpretacao",
            "delta_nao_equivale_a_melhora_ou_piora_sem_regra_especifica",
            "governanca_master_somente_leitura",
        ],
    }
