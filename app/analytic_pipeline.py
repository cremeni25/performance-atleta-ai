from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.agp_core_engine import Athlete, GlobalPerformanceEngine
from app.collection_instances import _participant
from app.participant_onboarding import _request, _require_owner, _single_row

router = APIRouter(prefix="/api/v1", tags=["analytic-pipeline"])

ENGINE_VERSION = "agp-core-v2.1-traceable"
ALLOWED_DOMAINS = {"fisico", "fisiologico", "tecnico", "mental", "recuperacao", "contextual"}


class AnalyticExecutionInput(BaseModel):
    participante_id: UUID
    coleta_ids: list[UUID] = Field(min_items=1)
    tipo: str = "score_global"
    parametros: dict[str, Any] = {}


def _validated_inputs(coleta_ids: list[UUID]) -> list[dict[str, Any]]:
    ids = ",".join(str(item) for item in coleta_ids)
    rows = _request("GET", "/rest/v1/agp_coletas", params={
        "id": f"in.({ids})",
        "select": "id,participante_id,atleta_id,projeto_id,protocolo_id,instrumento_id,status,completude,bloqueado_para_edicao,liberado_motor_em,hash_resposta,dados",
    })
    if len(rows or []) != len(set(coleta_ids)):
        raise HTTPException(status_code=422, detail="Uma ou mais coletas não foram encontradas")
    invalid = [
        row["id"] for row in rows
        if row.get("status") != "validada"
        or row.get("bloqueado_para_edicao") is not True
        or not row.get("liberado_motor_em")
    ]
    if invalid:
        raise HTTPException(status_code=422, detail={"codigo": "ENTRADA_ANALITICA_INVALIDA", "coletas": invalid})

    for row in rows:
        versions = _request("GET", "/rest/v1/agp_respostas_coleta_versoes", params={
            "coleta_id": f"eq.{row['id']}",
            "select": "id,numero_versao,dados,hash_resposta",
            "order": "numero_versao.desc",
            "limit": "1",
        })
        if not versions:
            raise HTTPException(status_code=422, detail=f"Coleta {row['id']} sem versão rastreável")
        row["versao"] = versions[0]
        protocols = _request(
            "GET",
            "/rest/v1/agp_protocolos",
            params={"id": f"eq.{row['protocolo_id']}", "select": "dominio"},
        )
        domain = (protocols[0].get("dominio") if protocols else None) or "contextual"
        row["dominio"] = "mental" if domain == "psicologico" else domain
    return rows


def _athlete_context(participant: dict[str, Any]) -> dict[str, Any]:
    baseline_rows = _request(
        "GET",
        "/rest/v1/agp_linhas_base_atleta",
        params={
            "participante_id": f"eq.{participant['id']}",
            "status": "in.(completa,validada)",
            "select": "idade_cronologica,categoria,data_referencia,status",
            "order": "data_referencia.desc",
            "limit": "1",
        },
    )
    profile_rows = _request(
        "GET",
        "/rest/v1/agp_perfis_esportivos",
        params={
            "pessoa_id": f"eq.{participant['pessoa_id']}",
            "status": "eq.ativo",
            "select": "nivel,categoria,modalidade",
            "limit": "1",
        },
    )

    baseline = baseline_rows[0] if baseline_rows else {}
    profile = profile_rows[0] if profile_rows else {}
    age = baseline.get("idade_cronologica")
    level = profile.get("nivel") or profile.get("categoria") or baseline.get("categoria")

    if age is None or not str(level or "").strip():
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "CONTEXTO_ATLETA_INSUFICIENTE",
                "mensagem": "A linha de base e o perfil esportivo precisam fornecer idade e nível antes do processamento analítico.",
            },
        )

    try:
        age_value = int(round(float(age)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Idade canônica inválida na linha de base") from exc

    if age_value < 5 or age_value > 100:
        raise HTTPException(status_code=422, detail="Idade canônica fora do intervalo operacional")

    return {
        "idade": age_value,
        "nivel": str(level).strip(),
        "modalidade": profile.get("modalidade"),
        "origem_idade": "agp_linhas_base_atleta",
        "origem_nivel": "agp_perfis_esportivos",
    }


def _numeric_values(value: Any) -> list[float]:
    values: list[float] = []
    if isinstance(value, bool):
        return [100.0 if value else 0.0]
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_numeric_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_numeric_values(item))
    return values


@router.get("/projetos/{projeto_id}/execucoes-analiticas")
def list_executions(projeto_id: UUID, authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_owner(authorization)
    rows = _request("GET", "/rest/v1/agp_execucoes_analiticas_operacionais", params={
        "projeto_id": f"eq.{projeto_id}",
        "select": "*",
        "order": "created_at.desc",
    })
    return rows if isinstance(rows, list) else []


@router.post("/execucoes-analiticas", status_code=status.HTTP_201_CREATED)
def execute_analysis(payload: AnalyticExecutionInput, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    participant = _participant(payload.participante_id)
    rows = _validated_inputs(payload.coleta_ids)
    if any(str(row["participante_id"]) != str(payload.participante_id) for row in rows):
        raise HTTPException(status_code=422, detail="Todas as coletas devem pertencer ao participante selecionado")

    context = _athlete_context(participant)
    normalized: dict[str, list[float]] = {domain: [] for domain in ALLOWED_DOMAINS}
    input_summary: list[dict[str, Any]] = []
    for order, row in enumerate(rows):
        domain = row["dominio"] if row["dominio"] in ALLOWED_DOMAINS else "contextual"
        values = _numeric_values(row["versao"]["dados"])
        if not values:
            raise HTTPException(status_code=422, detail=f"Coleta {row['id']} não contém valores numéricos analisáveis")
        normalized[domain].extend(values)
        input_summary.append({
            "coleta_id": row["id"],
            "versao_resposta_id": row["versao"]["id"],
            "dominio": domain,
            "hash": row["versao"].get("hash_resposta"),
            "ordem": order,
        })

    normalized = {key: value for key, value in normalized.items() if value}
    athlete = Athlete(profile={"idade": context["idade"], "nivel": context["nivel"]}, normalized_data=normalized)
    now = datetime.now(timezone.utc).isoformat()
    params = {**payload.parametros, "contexto_atleta": context}
    execution = _single_row(_request("POST", "/rest/v1/agp_execucoes_analiticas", payload={
        "participante_id": str(payload.participante_id),
        "atleta_id": participant["atleta_id"],
        "projeto_id": participant["projeto_id"],
        "tipo": payload.tipo,
        "versao_motor": ENGINE_VERSION,
        "status": "preparada",
        "parametros": params,
        "resumo_entradas": {"total": len(rows), "dominios": sorted(normalized.keys())},
        "solicitado_por": str(owner_id),
    }), "execução analítica")

    fingerprint_inputs = []
    for item in input_summary:
        stored = {**item}
        input_hash = stored.pop("hash") or "sem-hash"
        fingerprint_inputs.append({**stored, "hash": input_hash})
        _request("POST", "/rest/v1/agp_execucao_entradas", payload={
            "execucao_id": execution["id"],
            **stored,
            "hash_entrada": input_hash,
        })

    _request(
        "PATCH",
        "/rest/v1/agp_execucoes_analiticas",
        params={"id": f"eq.{execution['id']}"},
        payload={"status": "executando", "iniciado_em": now},
    )
    try:
        result = GlobalPerformanceEngine().run(athlete)
        fingerprint = hashlib.sha256(
            json.dumps({"motor": ENGINE_VERSION, "entradas": fingerprint_inputs, "parametros": params}, sort_keys=True, default=str).encode()
        ).hexdigest()
        explanation = result.get("diagnostico") or "Resultado multidimensional calculado com entradas explicitamente selecionadas."
        engine_confidence = result.get("confianca")
        confidence = float(engine_confidence) if isinstance(engine_confidence, (int, float)) else None
        final = _single_row(_request(
            "PATCH",
            "/rest/v1/agp_execucoes_analiticas",
            params={"id": f"eq.{execution['id']}"},
            payload={
                "status": "concluida",
                "resultado": result,
                "explicacao": explanation,
                "limitacoes": "O resultado depende da qualidade, escala e compatibilidade dos instrumentos selecionados; não substitui avaliação profissional.",
                "confianca": confidence,
                "hash_execucao": fingerprint,
                "concluido_em": datetime.now(timezone.utc).isoformat(),
            },
        ), "execução analítica")
        return final
    except HTTPException:
        raise
    except Exception as exc:
        _request(
            "PATCH",
            "/rest/v1/agp_execucoes_analiticas",
            params={"id": f"eq.{execution['id']}"},
            payload={"status": "falhou", "erro": str(exc), "concluido_em": datetime.now(timezone.utc).isoformat()},
        )
        raise HTTPException(status_code=500, detail="Falha controlada na execução analítica") from exc
