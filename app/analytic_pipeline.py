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
    idade: int = Field(ge=5, le=100)
    nivel: str = Field(min_length=2, max_length=80)
    tipo: str = "score_global"
    parametros: dict[str, Any] = {}


def _validated_inputs(coleta_ids: list[UUID]) -> list[dict[str, Any]]:
    ids = ",".join(str(item) for item in coleta_ids)
    rows = _request("GET", "/rest/v1/agp_coletas", params={
        "id": f"in.({ids})",
        "select": "id,participante_id,atleta_id,projeto_id,protocolo_id,instrumento_id,status,completude,bloqueada_em,liberado_motor_em,hash_resposta,dados",
    })
    if len(rows or []) != len(set(coleta_ids)):
        raise HTTPException(status_code=422, detail="Uma ou mais coletas não foram encontradas")
    invalid = [row["id"] for row in rows if row.get("status") != "validada" or not row.get("bloqueada_em") or not row.get("liberado_motor_em")]
    if invalid:
        raise HTTPException(status_code=422, detail={"codigo": "ENTRADA_ANALITICA_INVALIDA", "coletas": invalid})

    for row in rows:
        versions = _request("GET", "/rest/v1/agp_respostas_coleta_versoes", params={
            "coleta_id": f"eq.{row['id']}", "select": "id,numero_versao,dados,hash_resposta", "order": "numero_versao.desc", "limit": "1"
        })
        if not versions:
            raise HTTPException(status_code=422, detail=f"Coleta {row['id']} sem versão rastreável")
        row["versao"] = versions[0]
        protocols = _request("GET", "/rest/v1/agp_protocolos", params={"id": f"eq.{row['protocolo_id']}", "select": "dominio"})
        domain = (protocols[0].get("dominio") if protocols else None) or "contextual"
        row["dominio"] = "mental" if domain == "psicologico" else domain
    return rows


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
        "projeto_id": f"eq.{projeto_id}", "select": "*", "order": "created_at.desc"
    })
    return rows if isinstance(rows, list) else []


@router.post("/execucoes-analiticas", status_code=status.HTTP_201_CREATED)
def execute_analysis(payload: AnalyticExecutionInput, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    owner_id = _require_owner(authorization)
    participant = _participant(payload.participante_id)
    rows = _validated_inputs(payload.coleta_ids)
    if any(str(row["participante_id"]) != str(payload.participante_id) for row in rows):
        raise HTTPException(status_code=422, detail="Todas as coletas devem pertencer ao participante selecionado")

    normalized: dict[str, list[float]] = {domain: [] for domain in ALLOWED_DOMAINS}
    input_summary = []
    for order, row in enumerate(rows):
        domain = row["dominio"] if row["dominio"] in ALLOWED_DOMAINS else "contextual"
        values = _numeric_values(row["versao"]["dados"])
        if not values:
            raise HTTPException(status_code=422, detail=f"Coleta {row['id']} não contém valores numéricos analisáveis")
        normalized[domain].extend(values)
        input_summary.append({"coleta_id": row["id"], "versao_resposta_id": row["versao"]["id"], "dominio": domain, "hash": row["versao"].get("hash_resposta"), "ordem": order})

    normalized = {key: value for key, value in normalized.items() if value}
    athlete = Athlete(profile={"idade": payload.idade, "nivel": payload.nivel}, normalized_data=normalized)
    now = datetime.now(timezone.utc).isoformat()
    execution = _single_row(_request("POST", "/rest/v1/agp_execucoes_analiticas", payload={
        "participante_id": str(payload.participante_id), "atleta_id": participant["atleta_id"], "projeto_id": participant["projeto_id"],
        "tipo": payload.tipo, "versao_motor": ENGINE_VERSION, "status": "preparada", "parametros": {**payload.parametros, "idade": payload.idade, "nivel": payload.nivel},
        "resumo_entradas": {"total": len(rows), "dominios": sorted(normalized.keys())}, "solicitado_por": str(owner_id)
    }), "execução analítica")

    for item in input_summary:
        _request("POST", "/rest/v1/agp_execucao_entradas", payload={"execucao_id": execution["id"], **item, "hash_entrada": item.pop("hash") or "sem-hash"})

    _request("PATCH", "/rest/v1/agp_execucoes_analiticas", params={"id": f"eq.{execution['id']}"}, payload={"status": "executando", "iniciado_em": now})
    try:
        result = GlobalPerformanceEngine().run(athlete)
        fingerprint = hashlib.sha256(json.dumps({"motor": ENGINE_VERSION, "entradas": input_summary, "parametros": payload.parametros}, sort_keys=True, default=str).encode()).hexdigest()
        explanation = result.get("diagnostico") or "Resultado multidimensional calculado com entradas explicitamente selecionadas."
        final = _single_row(_request("PATCH", "/rest/v1/agp_execucoes_analiticas", params={"id": f"eq.{execution['id']}"}, payload={
            "status": "concluida", "resultado": result, "explicacao": explanation,
            "limitacoes": "O resultado depende da qualidade, escala e compatibilidade dos instrumentos selecionados; não substitui avaliação profissional.",
            "confianca": 100, "hash_execucao": fingerprint, "concluido_em": datetime.now(timezone.utc).isoformat()
        }), "execução analítica")
        return final
    except Exception as exc:
        _request("PATCH", "/rest/v1/agp_execucoes_analiticas", params={"id": f"eq.{execution['id']}"}, payload={"status": "falhou", "erro": str(exc), "concluido_em": datetime.now(timezone.utc).isoformat()})
        raise HTTPException(status_code=500, detail="Falha controlada na execução analítica") from exc
