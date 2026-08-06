from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Header, HTTPException, status

from app.participant_onboarding import _request, _require_owner, _single_row
from app.technical_team_management import _ensure_canonical_person

router = APIRouter(prefix="/api/v1", tags=["eligibility-management"])


def _age_from_birth_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        born = date.fromisoformat(value)
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _ensure_legacy_profile(person_id: str) -> str | None:
    profiles = _request(
        "GET",
        "/rest/v1/agp_perfis_esportivos",
        params={
            "pessoa_id": f"eq.{person_id}",
            "status": "eq.ativo",
            "select": "id,legacy_perfil_atleta_id,modalidade,categoria,nivel,dados_complementares",
            "limit": "1",
        },
    )
    if not profiles:
        return None
    profile = profiles[0]
    if profile.get("legacy_perfil_atleta_id"):
        return profile["legacy_perfil_atleta_id"]

    people = _request(
        "GET",
        "/rest/v1/agp_pessoas",
        params={"id": f"eq.{person_id}", "select": "nome,data_nascimento", "limit": "1"},
    )
    if not people:
        return None

    person = people[0]
    complementary = profile.get("dados_complementares") or {}
    payload = {
        "nome": person.get("nome") or "Atleta AGP",
        "idade": _age_from_birth_date(person.get("data_nascimento")),
        "nivel": profile.get("nivel"),
        "funcao": "Atleta",
        "tipo_usuario": "atleta",
        "esporte_id": complementary.get("esporte_id"),
        "modalidade_id": complementary.get("modalidade_id"),
        "esporte_slug": complementary.get("esporte_slug"),
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    legacy = _single_row(
        _request("POST", "/rest/v1/perfis_atletas", payload=payload),
        "perfil legado de compatibilidade",
    )
    legacy_id = legacy["id"]
    _request(
        "PATCH",
        "/rest/v1/agp_perfis_esportivos",
        params={"id": f"eq.{profile['id']}"},
        payload={"legacy_perfil_atleta_id": legacy_id},
    )
    return legacy_id


def _ensure_project_technician(project_id: UUID, technician_person_id: str, operator_id: UUID) -> None:
    current = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={
            "projeto_id": f"eq.{project_id}",
            "pessoa_id": f"eq.{technician_person_id}",
            "ativo": "eq.true",
            "select": "id",
            "limit": "1",
        },
    )
    if current:
        return

    roles = _request(
        "GET",
        "/rest/v1/agp_papeis_institucionais",
        params={
            "pessoa_id": f"eq.{technician_person_id}",
            "status": "eq.ativo",
            "select": "papel",
            "limit": "1",
        },
    )
    role = (roles[0].get("papel") if roles else None) or "tecnico"
    project_role = role if role in {"tecnico", "treinador", "preparador_fisico"} else "tecnico"
    _request(
        "POST",
        "/rest/v1/agp_participantes_projeto",
        payload={
            "projeto_id": str(project_id),
            "pessoa_id": technician_person_id,
            "funcao_no_projeto": project_role,
            "status_onboarding": "apto_para_coleta",
            "ativo": True,
            "criado_por": str(operator_id),
        },
    )


def _single_institution_technician(project_id: UUID, operator_id: UUID) -> str | None:
    projects = _request(
        "GET",
        "/rest/v1/agp_projetos_validacao",
        params={"id": f"eq.{project_id}", "select": "instituicao_id", "limit": "1"},
    )
    if not projects:
        return None
    institution_id = projects[0]["instituicao_id"]
    members = _request(
        "GET",
        "/rest/v1/agp_membros_instituicao",
        params={
            "instituicao_id": f"eq.{institution_id}",
            "ativo": "eq.true",
            "papel": "in.(admin_institucional,tecnico)",
            "select": "*",
        },
    )
    if not isinstance(members, list) or len(members) != 1:
        return None
    return str(_ensure_canonical_person(members[0], operator_id))


def _reconcile_project(project_id: UUID, operator_id: UUID) -> None:
    participants = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={
            "projeto_id": f"eq.{project_id}",
            "ativo": "eq.true",
            "select": "id,pessoa_id,funcao_no_projeto,tecnico_responsavel_pessoa_id",
        },
    )
    unique_technician_id: str | None = None
    for participant in participants or []:
        if participant.get("funcao_no_projeto") != "atleta":
            continue
        _ensure_legacy_profile(participant["pessoa_id"])
        technician_id = participant.get("tecnico_responsavel_pessoa_id")
        if not technician_id:
            if unique_technician_id is None:
                unique_technician_id = _single_institution_technician(project_id, operator_id)
            technician_id = unique_technician_id
            if technician_id:
                _request(
                    "PATCH",
                    "/rest/v1/agp_participantes_projeto",
                    params={"id": f"eq.{participant['id']}"},
                    payload={"tecnico_responsavel_pessoa_id": technician_id},
                )
        if technician_id:
            _ensure_project_technician(project_id, technician_id, operator_id)


@router.patch("/participantes/{participante_id}/tecnico-responsavel")
def assign_responsible_technician(
    participante_id: UUID,
    payload: dict[str, str] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    technician_id = payload.get("tecnico_responsavel_pessoa_id")
    if not technician_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Técnico responsável não informado")

    rows = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}", "select": "id,projeto_id,funcao_no_projeto", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado")
    participant = rows[0]
    if participant.get("funcao_no_projeto") != "atleta":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vínculo de técnico exige participante atleta")

    project_id = UUID(participant["projeto_id"])
    _ensure_project_technician(project_id, technician_id, operator_id)
    _request(
        "PATCH",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}"},
        payload={"tecnico_responsavel_pessoa_id": technician_id},
    )
    _reconcile_project(project_id, operator_id)
    result = _request(
        "POST",
        "/rest/v1/rpc/agp_elegibilidade_operacional",
        payload={"p_participante_id": str(participante_id)},
    )
    return result if isinstance(result, dict) else {"participante_id": str(participante_id), "tecnico_responsavel_pessoa_id": technician_id}


@router.get("/projetos/{projeto_id}/elegibilidade")
def list_project_eligibility(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    operator_id = _require_owner(authorization)
    _reconcile_project(projeto_id, operator_id)
    rows = _request(
        "GET",
        "/rest/v1/agp_elegibilidade_operacional_projeto",
        params={"projeto_id": f"eq.{projeto_id}", "select": "*", "order": "nome.asc"},
    )
    return rows if isinstance(rows, list) else []


@router.get("/participantes/{participante_id}/elegibilidade")
def get_participant_eligibility(
    participante_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    operator_id = _require_owner(authorization)
    rows = _request(
        "GET",
        "/rest/v1/agp_participantes_projeto",
        params={"id": f"eq.{participante_id}", "select": "projeto_id", "limit": "1"},
    )
    if rows:
        _reconcile_project(UUID(rows[0]["projeto_id"]), operator_id)
    result = _request(
        "POST",
        "/rest/v1/rpc/agp_elegibilidade_operacional",
        payload={"p_participante_id": str(participante_id)},
    )
    return result if isinstance(result, dict) else {
        "participante_id": str(participante_id),
        "apto_coleta": False,
        "apto_analise": False,
        "pendencias": ["elegibilidade_indisponivel"],
    }
