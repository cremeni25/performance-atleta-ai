from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.participant_onboarding import _request, _require_owner

router = APIRouter(prefix="/api/v1", tags=["athlete-intelligence"])


def _first(rows: Any) -> dict[str, Any] | None:
    return rows[0] if isinstance(rows, list) and rows else None


def _list(rows: Any) -> list[dict[str, Any]]:
    return rows if isinstance(rows, list) else []


def _next_action(
    *,
    participant: dict[str, Any],
    eligibility: dict[str, Any],
    collections: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    pending = eligibility.get("pendencias") or []

    if not participant.get("tecnico_responsavel_pessoa_id") or "tecnico_responsavel_pendente" in pending or "tecnico_responsavel_invalido" in pending:
        return {
            "codigo": "definir_tecnico",
            "titulo": "Definir técnico responsável",
            "descricao": "O atleta precisa de um responsável técnico válido antes de seguir na jornada.",
            "destino": "tecnico",
        }
    if "consentimento_pendente" in pending:
        return {
            "codigo": "regularizar_consentimento",
            "titulo": "Regularizar consentimento",
            "descricao": "O consentimento vigente é obrigatório para a operação esportiva do atleta.",
            "destino": "consentimento",
        }
    if "linha_base_pendente" in pending:
        return {
            "codigo": "registrar_linha_base",
            "titulo": "Completar linha de base",
            "descricao": "A referência inicial do atleta precisa ser registrada antes da análise longitudinal.",
            "destino": "linha-base",
        }
    if "instrumento_indisponivel" in pending:
        return {
            "codigo": "ativar_instrumento",
            "titulo": "Ativar instrumento compatível",
            "descricao": "O atleta está preparado, mas não existe instrumento científico ativo compatível com seu contexto esportivo.",
            "destino": "catalogo-cientifico",
        }

    valid_collections = [item for item in collections if item.get("status") == "validada"]
    open_collections = [item for item in collections if item.get("status") in {"rascunho", "completa"}]

    if eligibility.get("apto_coleta") and not collections:
        return {
            "codigo": "iniciar_coleta",
            "titulo": "Iniciar primeira coleta",
            "descricao": "O atleta está elegível e já pode gerar evidência real para o motor de inteligência.",
            "destino": "coletas",
        }
    if open_collections:
        return {
            "codigo": "concluir_coleta",
            "titulo": "Concluir coleta em andamento",
            "descricao": "Existe uma coleta ainda não validada. Complete e valide antes de avançar.",
            "destino": "coletas",
        }
    if eligibility.get("apto_analise") and valid_collections and not executions:
        return {
            "codigo": "executar_analise",
            "titulo": "Executar análise",
            "descricao": "Já existe evidência validada e liberada para o motor analítico.",
            "destino": "pipeline-analitico",
        }

    pending_validation = [item for item in results if item.get("status") == "preliminar"]
    if pending_validation:
        return {
            "codigo": "validar_resultado",
            "titulo": "Validar resultado analítico",
            "descricao": "O motor já produziu um resultado e ele aguarda validação profissional.",
            "destino": "validacao-profissional",
        }

    validated = [item for item in results if item.get("status") == "validado"]
    if validated:
        return {
            "codigo": "aplicar_resultado",
            "titulo": "Aplicar resultado ao atleta",
            "descricao": "Existe resultado validado. O foco passa a ser a aplicação prática e o próximo ciclo de acompanhamento.",
            "destino": "resultado-validado",
        }

    return {
        "codigo": "revisar_jornada",
        "titulo": "Revisar jornada do atleta",
        "descricao": "O sistema não identificou uma próxima ação automática. Revise elegibilidade, coletas e resultados.",
        "destino": "elegibilidade",
    }


@router.get("/participantes/{participante_id}/inteligencia")
def get_athlete_intelligence(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_owner(authorization)

    participant = _first(
        _request(
            "GET",
            "/rest/v1/agp_participantes_projeto",
            params={
                "id": f"eq.{participante_id}",
                "select": "id,pessoa_id,projeto_id,funcao_no_projeto,status_onboarding,ativo,tecnico_responsavel_pessoa_id,data_inicio",
                "limit": "1",
            },
        )
    )
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    if participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O participante selecionado não é atleta")

    person = _first(
        _request(
            "GET",
            "/rest/v1/agp_pessoas",
            params={"id": f"eq.{participant['pessoa_id']}", "select": "*", "limit": "1"},
        )
    ) or {}
    project = _first(
        _request(
            "GET",
            "/rest/v1/agp_projetos_validacao",
            params={"id": f"eq.{participant['projeto_id']}", "select": "*", "limit": "1"},
        )
    ) or {}
    institution = {}
    if project.get("instituicao_id"):
        institution = _first(
            _request(
                "GET",
                "/rest/v1/agp_instituicoes",
                params={"id": f"eq.{project['instituicao_id']}", "select": "*", "limit": "1"},
            )
        ) or {}

    profile = _first(
        _request(
            "GET",
            "/rest/v1/agp_perfis_esportivos",
            params={
                "pessoa_id": f"eq.{participant['pessoa_id']}",
                "status": "eq.ativo",
                "select": "*",
                "limit": "1",
            },
        )
    ) or {}

    technician = {}
    if participant.get("tecnico_responsavel_pessoa_id"):
        technician = _first(
            _request(
                "GET",
                "/rest/v1/agp_pessoas",
                params={
                    "id": f"eq.{participant['tecnico_responsavel_pessoa_id']}",
                    "select": "id,nome,email_contato,telefone_contato,status",
                    "limit": "1",
                },
            )
        ) or {}

    eligibility_raw = _request(
        "POST",
        "/rest/v1/rpc/agp_elegibilidade_operacional",
        payload={"p_participante_id": str(participante_id)},
    )
    eligibility = eligibility_raw if isinstance(eligibility_raw, dict) else {}

    collections = _list(
        _request(
            "GET",
            "/rest/v1/agp_coletas_operacionais",
            params={
                "participante_id": f"eq.{participante_id}",
                "select": "*",
                "order": "data_hora_coleta.desc",
                "limit": "20",
            },
        )
    )
    executions = _list(
        _request(
            "GET",
            "/rest/v1/agp_execucoes_analiticas_operacionais",
            params={
                "participante_id": f"eq.{participante_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": "10",
            },
        )
    )

    athlete_id = profile.get("legacy_perfil_atleta_id")
    results: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    if athlete_id:
        results = _list(
            _request(
                "GET",
                "/rest/v1/agp_resultados_analiticos",
                params={
                    "atleta_id": f"eq.{athlete_id}",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": "10",
                },
            )
        )
        scores = _list(
            _request(
                "GET",
                "/rest/v1/score_atleta",
                params={
                    "atleta_id": f"eq.{athlete_id}",
                    "select": "*",
                    "order": "data_calculo.desc",
                    "limit": "5",
                },
            )
        )

    latest_result = results[0] if results else None
    latest_score = scores[0] if scores else None
    latest_collection = collections[0] if collections else None
    next_action = _next_action(
        participant=participant,
        eligibility=eligibility,
        collections=collections,
        executions=executions,
        results=results,
    )

    journey = {
        "preparacao": {
            "concluida": bool(
                participant.get("ativo")
                and participant.get("tecnico_responsavel_pessoa_id")
                and eligibility.get("consentimento_vigente")
                and eligibility.get("linha_base_vigente")
            ),
            "status_onboarding": participant.get("status_onboarding"),
        },
        "coleta": {
            "elegivel": bool(eligibility.get("apto_coleta")),
            "total": len(collections),
            "validadas": len([item for item in collections if item.get("status") == "validada"]),
            "ultima": latest_collection,
        },
        "analise": {
            "elegivel": bool(eligibility.get("apto_analise")),
            "total_execucoes": len(executions),
            "ultima": executions[0] if executions else None,
        },
        "validacao": {
            "total_resultados": len(results),
            "ultimo_resultado": latest_result,
            "resultado_validado": bool(latest_result and latest_result.get("status") == "validado"),
        },
        "aplicacao": {
            "score_atual": latest_score,
            "resultado_aplicavel": latest_result if latest_result and latest_result.get("status") == "validado" else None,
        },
    }

    return {
        "participante": participant,
        "pessoa": person,
        "projeto": project,
        "instituicao": institution,
        "perfil_esportivo": profile,
        "tecnico": technician,
        "elegibilidade": eligibility,
        "jornada": journey,
        "proxima_acao": next_action,
        "coletas_recentes": collections[:5],
        "execucoes_recentes": executions[:5],
        "resultados_recentes": results[:5],
        "scores_recentes": scores[:5],
    }
