from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import sqrt
from statistics import mean, pstdev
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1", tags=["individual-intelligence-v3"])

READINESS_FIELDS = {
    "sono_horas": {"direction": "high_good", "label": "Sono"},
    "qualidade_sono": {"direction": "high_good", "label": "Qualidade do sono"},
    "fadiga": {"direction": "low_good", "label": "Fadiga"},
    "dor": {"direction": "low_good", "label": "Dor"},
    "estresse": {"direction": "low_good", "label": "Estresse"},
    "humor": {"direction": "high_good", "label": "Humor"},
    "rpe_ultima_sessao": {"direction": "context", "label": "Esforço percebido"},
}


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    mx, my = mean(xs), mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den == 0:
        return None
    return round(sum(x * y for x, y in zip(dx, dy)) / den, 3)


def _trend(values: list[float]) -> dict[str, Any]:
    if len(values) < 3:
        return {"status": "insuficiente", "amostras": len(values), "direcao": None}
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0.0
    spread = pstdev(values) if len(values) > 1 else 0.0
    relative = slope / spread if spread > 0 else 0.0
    direction = "estavel"
    if relative >= 0.25:
        direction = "subindo"
    elif relative <= -0.25:
        direction = "caindo"
    return {
        "status": "calculada",
        "amostras": n,
        "direcao": direction,
        "inclinacao": round(slope, 3),
        "variabilidade": round(spread, 3),
    }


def _readiness_analysis(collections: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in collections if c.get("status") == "validada" and isinstance(c.get("dados"), dict)]
    valid.sort(key=lambda c: str(c.get("data_hora_coleta") or c.get("created_at") or ""))
    if not valid:
        return {
            "status": "sem_evidencia",
            "amostras": 0,
            "baseline_pessoal": {},
            "ultimo_registro": None,
            "tendencias": {},
            "sinais": [],
            "relacoes": [],
        }

    by_field: dict[str, list[float]] = {key: [] for key in READINESS_FIELDS}
    for item in valid:
        dados = item.get("dados") or {}
        for key in by_field:
            value = _number(dados.get(key))
            if value is not None:
                by_field[key].append(value)

    baseline: dict[str, Any] = {}
    trends: dict[str, Any] = {}
    latest_data = valid[-1].get("dados") or {}
    signals: list[dict[str, Any]] = []

    for key, config in READINESS_FIELDS.items():
        values = by_field[key]
        base_values = values[: min(7, len(values))]
        base = mean(base_values) if base_values else None
        latest = _number(latest_data.get(key))
        delta = latest - base if latest is not None and base is not None else None
        baseline[key] = {
            "rotulo": config["label"],
            "media_pessoal": round(base, 2) if base is not None else None,
            "ultimo": round(latest, 2) if latest is not None else None,
            "desvio_atual": round(delta, 2) if delta is not None else None,
            "amostras_baseline": len(base_values),
        }
        trends[key] = _trend(values[-7:])

    sleep = _number(latest_data.get("sono_horas"))
    fatigue = _number(latest_data.get("fadiga"))
    pain = _number(latest_data.get("dor"))
    stress = _number(latest_data.get("estresse"))
    mood = _number(latest_data.get("humor"))
    rpe = _number(latest_data.get("rpe_ultima_sessao"))

    if pain is not None and pain >= 7:
        signals.append({"nivel": "alto", "dominio": "dor", "mensagem": "Dor autorreferida elevada; requer revisão profissional antes de decisões de carga."})
    elif pain is not None and pain >= 4:
        signals.append({"nivel": "atencao", "dominio": "dor", "mensagem": "Dor acima da faixa baixa habitual; acompanhar evolução e contexto."})
    if sleep is not None and sleep < 6:
        signals.append({"nivel": "atencao", "dominio": "recuperacao", "mensagem": "Sono abaixo de 6 horas no registro mais recente."})
    if fatigue is not None and fatigue >= 4:
        signals.append({"nivel": "atencao", "dominio": "recuperacao", "mensagem": "Fadiga percebida elevada no registro mais recente."})
    if stress is not None and stress >= 4:
        signals.append({"nivel": "atencao", "dominio": "contextual", "mensagem": "Estresse percebido elevado no registro mais recente."})
    if mood is not None and mood <= 2:
        signals.append({"nivel": "atencao", "dominio": "mental", "mensagem": "Humor autorreferido baixo; interpretar junto ao contexto e ao acompanhamento profissional."})
    if rpe is not None and fatigue is not None and rpe >= 8 and fatigue >= 4:
        signals.append({"nivel": "atencao", "dominio": "carga_recuperacao", "mensagem": "Esforço percebido alto coexistindo com fadiga elevada; revisar recuperação antes da próxima carga intensa."})

    relations: list[dict[str, Any]] = []
    rpe_values = by_field["rpe_ultima_sessao"]
    fatigue_values = by_field["fadiga"]
    if len(rpe_values) == len(fatigue_values):
        corr = _pearson(rpe_values[-14:], fatigue_values[-14:])
        if corr is not None:
            relations.append({
                "entre": ["rpe_ultima_sessao", "fadiga"],
                "coeficiente": corr,
                "forca": "forte" if abs(corr) >= 0.7 else "moderada" if abs(corr) >= 0.4 else "fraca",
                "nota": "Associação observacional individual; não implica causalidade.",
            })

    return {
        "status": "baseline_em_formacao" if len(valid) < 3 else "longitudinal",
        "amostras": len(valid),
        "baseline_pessoal": baseline,
        "ultimo_registro": valid[-1],
        "tendencias": trends,
        "sinais": signals,
        "relacoes": relations,
    }


def _coverage(collections: list[dict[str, Any]], sessions: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)
    recent_valid = [c for c in collections if c.get("status") == "validada" and (_iso(c.get("data_hora_coleta")) or now) >= cutoff]
    dates = {(_iso(c.get("data_hora_coleta")) or now).date().isoformat() for c in recent_valid}
    readiness_coverage = min(100.0, len(dates) * 100.0 / 14.0)
    completeness = mean([float(c.get("completude") or 0) for c in recent_valid]) if recent_valid else 0.0
    reliability_values = [float(c.get("confiabilidade")) for c in recent_valid if c.get("confiabilidade") is not None]
    reliability = mean(reliability_values) if reliability_values else (100.0 if recent_valid and completeness >= 100 else 0.0)
    training_present = bool(sessions)
    validated_result = any(r.get("status") == "validado" for r in results)
    confidence = 0.45 * readiness_coverage + 0.30 * completeness + 0.15 * reliability + (5 if training_present else 0) + (5 if validated_result else 0)
    confidence = round(min(100.0, confidence), 1)
    label = "baixa"
    if confidence >= 75:
        label = "alta"
    elif confidence >= 45:
        label = "moderada"
    return {
        "janela_dias": 14,
        "dias_com_evidencia_validada": len(dates),
        "cobertura_percentual": round(readiness_coverage, 1),
        "completude_media": round(completeness, 1),
        "confiabilidade_media": round(reliability, 1),
        "sessoes_treino_disponiveis": len(sessions),
        "resultado_profissional_validado": validated_result,
        "confianca_geral": confidence,
        "classificacao_confianca": label,
    }


def _practical_return(readiness: dict[str, Any], coverage: dict[str, Any], sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if readiness["amostras"] == 0:
        return {
            "estado": "aguardando_evidencia",
            "mensagem": "Ainda não há evidência validada suficiente para interpretar o estado individual do atleta.",
            "acao_prioritaria": "Realizar e validar a primeira coleta de prontidão diária.",
            "limites": ["Nenhuma tendência individual pode ser inferida sem registros reais."],
        }
    if readiness["amostras"] < 3:
        return {
            "estado": "baseline_em_formacao",
            "mensagem": "O AGP já iniciou a leitura individual, mas ainda está formando a referência pessoal do atleta.",
            "acao_prioritaria": "Manter coletas consistentes até haver pelo menos três registros válidos antes de interpretar tendência.",
            "limites": ["Amostra ainda pequena para concluir tendência ou relação entre variáveis."],
        }

    high = [s for s in readiness["sinais"] if s["nivel"] == "alto"]
    attention = [s for s in readiness["sinais"] if s["nivel"] == "atencao"]
    if high:
        return {
            "estado": "revisao_profissional_prioritaria",
            "mensagem": high[0]["mensagem"],
            "acao_prioritaria": "Priorizar revisão profissional contextualizada antes de intensificar a carga.",
            "limites": ["Sinal operacional, não diagnóstico clínico automático."],
        }
    if attention:
        return {
            "estado": "atencao_contextual",
            "mensagem": "Há sinais que merecem acompanhamento conjunto entre atleta e equipe.",
            "acao_prioritaria": "Revisar recuperação, carga recente e contexto antes da próxima decisão de treino.",
            "limites": ["A recomendação depende da qualidade e regularidade dos dados autorreferidos."],
        }
    if coverage["classificacao_confianca"] == "baixa":
        return {
            "estado": "estavel_com_baixa_confianca",
            "mensagem": "Não há sinal forte no registro atual, mas a cobertura ainda é insuficiente para uma devolução robusta.",
            "acao_prioritaria": "Aumentar regularidade das coletas e registrar sessões de treino.",
            "limites": ["Ausência de sinal não significa ausência de risco quando a cobertura é baixa."],
        }
    return {
        "estado": "acompanhamento_regular",
        "mensagem": "A evidência disponível não mostra sinal operacional crítico neste momento.",
        "acao_prioritaria": "Manter monitoramento e relacionar a prontidão com as próximas sessões e resultados esportivos.",
        "limites": [] if sessions else ["Ainda faltam sessões de treino estruturadas para relacionar prontidão e carga."],
    }


@router.get("/participantes/{participante_id}/inteligencia-v3")
def get_individual_intelligence_v3(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_owner(authorization)

    participant = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "id": f"eq.{participante_id}",
        "select": "id,pessoa_id,projeto_id,funcao_no_projeto,legacy_perfil_atleta_id,status_onboarding,ativo",
        "limit": "1",
    }))
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    if participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Participante não é atleta")

    athlete_id = participant.get("legacy_perfil_atleta_id")
    collections = _rows(_request("GET", "/rest/v1/agp_coletas", params={
        "participante_id": f"eq.{participante_id}",
        "select": "id,participante_id,atleta_id,projeto_id,instrumento_id,data_hora_coleta,status,completude,confiabilidade,dados,origem,liberado_motor_em,created_at",
        "order": "data_hora_coleta.asc",
        "limit": "100",
    }))

    sessions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    interventions: list[dict[str, Any]] = []
    if athlete_id:
        sessions = _rows(_request("GET", "/rest/v1/agp_sessoes_treinamento", params={
            "atleta_id": f"eq.{athlete_id}",
            "select": "*",
            "order": "data_hora_inicio.desc",
            "limit": "30",
        }))
        results = _rows(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
            "atleta_id": f"eq.{athlete_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": "20",
        }))
        interventions = _rows(_request("GET", "/rest/v1/agp_intervencoes", params={
            "atleta_id": f"eq.{athlete_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": "20",
        }))

    readiness = _readiness_analysis(collections)
    coverage = _coverage(collections, sessions, results)
    practical = _practical_return(readiness, coverage, sessions)

    missing: list[str] = []
    if readiness["amostras"] == 0:
        missing.append("primeira_coleta_validada")
    elif readiness["amostras"] < 3:
        missing.append("baseline_longitudinal_minimo")
    if not sessions:
        missing.append("sessoes_treinamento")
    if not results:
        missing.append("resultado_analitico_validado")

    return {
        "versao_motor": "AGP-INDIVIDUAL-3.0.0",
        "metodo": "longitudinal_individual_explicavel",
        "principio": "comparar_prioritariamente_o_atleta_com_ele_mesmo",
        "participante_id": str(participante_id),
        "atleta_id": athlete_id,
        "cobertura": coverage,
        "prontidao_individual": readiness,
        "devolucao_pratica": practical,
        "dados_ausentes_relevantes": missing,
        "sessoes_recentes": sessions[:5],
        "resultados_recentes": results[:5],
        "intervencoes_recentes": interventions[:5],
        "governanca": {
            "sem_dados_simulados": True,
            "nao_diagnostico_clinico": True,
            "exige_validacao_profissional_para_resultado_final": True,
        },
    }
