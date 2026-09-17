from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person
from app.canonical_professional_assessment import _authorize_professional

router = APIRouter(prefix="/api/v1", tags=["canonical-professional-validation"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _first(value: Any) -> dict[str, Any] | None:
    rows = _rows(value)
    return rows[0] if rows else None


def _result(resultado_id: UUID) -> dict[str, Any]:
    row = _first(_request("GET", "/rest/v1/agp_resultados_analiticos", params={
        "id": f"eq.{resultado_id}",
        "select": "id,atleta_id,projeto_id,tipo,versao_motor,protocolo_id,entradas,resultado,explicacao,confianca,limitacoes,status,created_at",
        "limit": "1",
    }))
    if not row:
        raise HTTPException(status_code=404, detail="Resultado analítico não encontrado")
    if not row.get("projeto_id"):
        raise HTTPException(status_code=422, detail="Resultado analítico sem contexto de projeto")
    return row


def _participant_from_result(result: dict[str, Any]) -> dict[str, Any]:
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "legacy_perfil_atleta_id": f"eq.{result['atleta_id']}",
        "status": "eq.ativo",
        "select": "pessoa_id",
        "limit": "1",
    }))
    if not profile:
        raise HTTPException(status_code=422, detail="Resultado ainda não reconciliado com a identidade canônica")
    participant = _first(_request("GET", "/rest/v1/agp_participantes_projeto", params={
        "pessoa_id": f"eq.{profile['pessoa_id']}",
        "projeto_id": f"eq.{result['projeto_id']}",
        "funcao_no_projeto": "eq.atleta",
        "ativo": "eq.true",
        "select": "id,pessoa_id,projeto_id,funcao_no_projeto",
        "limit": "1",
    }))
    if not participant:
        raise HTTPException(status_code=422, detail="Resultado ainda não reconciliado com participante canônico")
    return participant


def _domains_from_result(result: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    protocol_id = result.get("protocolo_id")
    if protocol_id:
        protocol = _first(_request("GET", "/rest/v1/agp_protocolos", params={
            "id": f"eq.{protocol_id}", "select": "dominio", "limit": "1",
        }))
        if protocol and protocol.get("dominio"):
            domains.append(str(protocol["dominio"]))

    entries = result.get("entradas") or []
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, dict) and item.get("dominio"):
                domains.append(str(item["dominio"]))

    normalized: list[str] = []
    mapping = {
        "mental": "psicologico",
        "psychological": "psicologico",
        "medical": "medico",
        "nutrition": "nutricional",
        "physiology": "fisiologico",
        "physical": "fisico",
        "technical": "tecnico",
        "recovery": "recuperacao",
        "context": "contextual",
    }
    for domain in domains:
        value = mapping.get(domain.strip().lower(), domain.strip().lower())
        if value and value not in normalized:
            normalized.append(value)
    return normalized or ["contextual"]


def _resolve_scope(actor_pessoa_id: str, participant: dict[str, Any], result: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]]:
    domains = _domains_from_result(result)
    errors: list[str] = []
    for domain in domains:
        try:
            scope = _authorize_professional(actor_pessoa_id, participant, domain)
            return scope, domain, domains
        except HTTPException as exc:
            errors.append(str(exc.detail))
    raise HTTPException(
        status_code=403,
        detail={
            "codigo": "ESCOPO_PROFISSIONAL_INCOMPATIVEL",
            "mensagem": "O resultado existe, mas a pessoa autenticada não possui competência válida para emitir parecer sobre nenhum dos seus domínios.",
            "dominios_resultado": domains,
        },
    )


class CanonicalProfessionalValidationInput(BaseModel):
    decisao: str = Field(regex="^(aprovado|rejeitado|substituido)$")
    parecer_tecnico: str = Field(min_length=10, max_length=5000)
    substitui_resultado_id: UUID | None = None
    motivo_substituicao: str | None = Field(default=None, max_length=3000)


@router.get("/resultados/{resultado_id}/validacoes-canonicas")
def list_canonical_validations(resultado_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    result = _result(resultado_id)
    participant = _participant_from_result(result)

    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]):
        contexts = _rows(_request("GET", "/rest/v1/agp_contextos_identidade_efetivos", params={
            "pessoa_id": f"eq.{actor['pessoa_id']}",
            "projeto_id": f"eq.{participant['projeto_id']}",
            "status": "eq.ativo",
            "select": "papel_codigo",
            "limit": "1",
        }))
        if not contexts:
            raise HTTPException(status_code=403, detail="Sem vínculo ativo com o contexto do atleta")

    validations = _rows(_request("GET", "/rest/v1/agp_validacoes_profissionais_canonicas", params={
        "resultado_id": f"eq.{resultado_id}",
        "select": "*",
        "order": "created_at.desc",
    }))
    return {
        "modelo": "AGP-Professional-Validation-v2",
        "resultado_id": str(resultado_id),
        "validacoes": validations,
        "principio": "o_usuario_registra_parecer_e_decisao_o_agp_resolve_o_contexto",
    }


@router.post("/resultados/{resultado_id}/validacoes-canonicas", status_code=status.HTTP_201_CREATED)
def create_canonical_validation(
    resultado_id: UUID,
    payload: CanonicalProfessionalValidationInput,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    result = _result(resultado_id)
    participant = _participant_from_result(result)
    scope, validated_domain, result_domains = _resolve_scope(str(actor["pessoa_id"]), participant, result)

    if payload.decisao == "substituido" and not payload.substitui_resultado_id:
        raise HTTPException(status_code=422, detail="Resultado substituto é obrigatório quando a decisão for substituído")
    if payload.decisao != "substituido" and payload.substitui_resultado_id:
        raise HTTPException(status_code=422, detail="Resultado substituto só deve ser informado quando a decisão for substituído")

    if payload.substitui_resultado_id:
        replacement = _result(payload.substitui_resultado_id)
        replacement_participant = _participant_from_result(replacement)
        if str(replacement_participant["id"]) != str(participant["id"]):
            raise HTTPException(status_code=422, detail="Resultado substituto pertence a outro atleta")

    context_snapshot = {
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "dominios_resultado": result_domains,
        "dominio_validado": validated_domain,
    }
    scope_snapshot = {
        "competencia_codigo": scope["competencia_codigo"],
        "papel_codigo": scope["papel_codigo"],
        "credencial_verificada": scope["credencial_verificada"],
        "requer_credencial": scope["requer_credencial"],
    }

    created = _first(_request("POST", "/rest/v1/agp_validacoes_profissionais", payload={
        "resultado_id": str(resultado_id),
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "projeto_id": participant["projeto_id"],
        "decisao": payload.decisao,
        "parecer_tecnico": payload.parecer_tecnico,
        "papel_profissional": scope["papel_codigo"],
        "competencia_codigo": scope["competencia_codigo"],
        "credencial_verificada_no_registro": scope["credencial_verificada"],
        "natureza_validacao": "profissional_contexto_derivado",
        "evidencia_referencia": [],
        "escopo_derivado": scope_snapshot,
        "contexto_derivado": context_snapshot,
        "profissional_auth_id": str(user["id"]),
        "visivel_atleta": False,
        "visivel_comissao": True,
        "visivel_instituicao": True,
        "substitui_resultado_id": str(payload.substitui_resultado_id) if payload.substitui_resultado_id else None,
        "motivo_substituicao": payload.motivo_substituicao,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar validação profissional")

    _request("PATCH", "/rest/v1/agp_resultados_analiticos", params={"id": f"eq.{resultado_id}"}, payload={
        "status": "validado" if payload.decisao == "aprovado" else "rejeitado" if payload.decisao == "rejeitado" else "substituido",
        "validado_por_auth_id": str(user["id"]),
        "parecer_tecnico": payload.parecer_tecnico,
        "decisao_profissional": payload.decisao,
        "papel_validador": scope["papel_codigo"],
        "visivel_atleta": False,
        "visivel_comissao": True,
        "visivel_instituicao": True,
        "substitui_resultado_id": str(payload.substitui_resultado_id) if payload.substitui_resultado_id else None,
        "motivo_substituicao": payload.motivo_substituicao,
    })

    return {
        "validacao": created,
        "entrada_humana": {
            "parecer": payload.parecer_tecnico,
            "decisao": payload.decisao,
        },
        "resolvido_pelo_agp": {
            "contexto": context_snapshot,
            "escopo_profissional": scope_snapshot,
        },
        "principio": "rastreabilidade_profunda_sem_friccao_operacional",
    }
