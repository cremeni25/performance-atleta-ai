from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request, _single_row
from app.canonical_longitudinal_intelligence import _actor_person
from app.canonical_training_planning import _project_scope

router = APIRouter(prefix="/api/v1", tags=["coach-athlete-onboarding"])


def _rows(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


class CoachAthleteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=320)
    data_nascimento: date | None = None
    categoria: str | None = Field(default=None, max_length=120)
    nivel: str | None = Field(default=None, max_length=120)
    prova_principal: str | None = Field(default=None, max_length=120)
    status_federativo: Literal["nao_informado", "vinculado", "federado"] = "nao_informado"
    federacao_nome: str | None = Field(default=None, max_length=200)
    registro_federativo: str | None = Field(default=None, max_length=160)


def _project(projeto_id: UUID) -> dict[str, Any]:
    project = _rows(_request("GET", "/rest/v1/agp_projetos_validacao", params={
        "id": f"eq.{projeto_id}",
        "select": "id,instituicao_id,nome,status",
        "limit": "1",
    }))
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project[0]


def _invite(email: str, participant_id: str, person_id: str) -> str:
    frontend_url = os.getenv("AGP_FRONTEND_URL", "https://agp-frontend-vite.onrender.com/").rstrip("/") + "/"
    invited = _request(
        "POST",
        "/auth/v1/invite",
        params={"redirect_to": frontend_url},
        payload={
            "email": email,
            "data": {
                "agp_participante_id": participant_id,
                "agp_pessoa_id": person_id,
                "tipo_usuario": "atleta",
            },
        },
    )
    auth_id = invited.get("id") if isinstance(invited, dict) else None
    if not auth_id:
        raise HTTPException(status_code=502, detail="Serviço de autenticação não retornou o atleta convidado")
    return str(auth_id)


@router.get("/projetos/{projeto_id}/atletas-piloto")
def list_pilot_athletes(
    projeto_id: UUID,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(projeto_id), {"training.plan", "training.record"})
    project = _project(projeto_id)

    athletes = _rows(_request("GET", "/rest/v1/agp_participantes_elegibilidade", params={
        "projeto_id": f"eq.{projeto_id}",
        "funcao_no_projeto": "eq.atleta",
        "ativo": "eq.true",
        "select": "*",
        "order": "nome.asc",
    }))

    person_ids = [str(x["pessoa_id"]) for x in athletes if x.get("pessoa_id")]
    accounts = _rows(_request("GET", "/rest/v1/agp_contas_acesso", params={
        "pessoa_id": f"in.({','.join(person_ids)})",
        "select": "id,pessoa_id,email_acesso,status,auth_id",
    })) if person_ids else []
    account_map = {str(x["pessoa_id"]): x for x in accounts}

    return {
        "projeto": project,
        "escopo_profissional": scope,
        "atletas": [
            {
                **athlete,
                "acesso": account_map.get(str(athlete.get("pessoa_id"))),
            }
            for athlete in athletes
        ],
    }


@router.post("/projetos/{projeto_id}/atletas-piloto", status_code=status.HTTP_201_CREATED)
def create_and_invite_pilot_athlete(
    projeto_id: UUID,
    payload: CoachAthleteCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    scope = _project_scope(str(actor["pessoa_id"]), str(projeto_id), {"training.plan"})
    project = _project(projeto_id)
    institution_id = str(project["instituicao_id"])

    email = payload.email.strip().lower()
    duplicate = _rows(_request("GET", "/rest/v1/agp_contas_acesso", params={
        "email_acesso": f"eq.{email}",
        "select": "id,pessoa_id,auth_id,status",
        "limit": "1",
    }))
    if duplicate:
        raise HTTPException(status_code=409, detail="Este e-mail já está vinculado a uma identidade AGP")

    person = _single_row(_request("POST", "/rest/v1/agp_pessoas", payload={
        "nome": payload.nome.strip(),
        "data_nascimento": payload.data_nascimento.isoformat() if payload.data_nascimento else None,
        "email_contato": email,
        "status": "ativo",
        "criado_por": str(user["id"]),
    }), "atleta")
    person_id = str(person["id"])

    try:
        role = _single_row(_request("POST", "/rest/v1/agp_papeis_institucionais", payload={
            "pessoa_id": person_id,
            "instituicao_id": institution_id,
            "papel": "atleta",
            "papel_codigo": "athlete",
            "escopo": {"origem": "tecnico_projeto_piloto", "projeto_id": str(projeto_id)},
            "status": "ativo",
            "criado_por": str(user["id"]),
        }), "papel de atleta")

        account = _single_row(_request("POST", "/rest/v1/agp_contas_acesso", payload={
            "pessoa_id": person_id,
            "auth_id": None,
            "email_acesso": email,
            "status": "acesso_pendente",
        }), "conta do atleta")

        profile = _single_row(_request("POST", "/rest/v1/agp_perfis_esportivos", payload={
            "pessoa_id": person_id,
            "modalidade": "Natação Piscina",
            "prova_posicao": payload.prova_principal,
            "categoria": payload.categoria,
            "nivel": payload.nivel,
            "status_federativo": payload.status_federativo,
            "federacao_nome": payload.federacao_nome if payload.status_federativo == "federado" else None,
            "registro_federativo": payload.registro_federativo if payload.status_federativo == "federado" else None,
            "status_federativo_atualizado_em": datetime.now(timezone.utc).isoformat(),
            "status": "ativo",
            "dados_complementares": {"origem": "piloto_n1_tecnico"},
        }), "perfil esportivo")

        participant = _single_row(_request("POST", "/rest/v1/agp_participantes_projeto", payload={
            "projeto_id": str(projeto_id),
            "pessoa_id": person_id,
            "funcao_no_projeto": "atleta",
            "funcao_canonica_codigo": "athlete",
            "tecnico_responsavel_pessoa_id": str(actor["pessoa_id"]),
            "status_onboarding": "consentimento_pendente",
            "ativo": True,
            "criado_por": str(user["id"]),
        }), "vínculo do atleta")
        participant_id = str(participant["id"])

        auth_id = _invite(email, participant_id, person_id)

        linked = _single_row(_request("PATCH", "/rest/v1/agp_contas_acesso", params={
            "id": f"eq.{account['id']}",
            "auth_id": "is.null",
        }, payload={
            "auth_id": auth_id,
        }), "vínculo de autenticação")

        _request("POST", "/rest/v1/agp_auditoria_participantes", payload={
            "pessoa_id": person_id,
            "projeto_id": str(projeto_id),
            "acao": "atleta_piloto_criado_e_convidado_por_tecnico",
            "estado_novo": {
                "papel": "atleta",
                "status_onboarding": "consentimento_pendente",
                "email_acesso": email,
                "tecnico_responsavel_pessoa_id": str(actor["pessoa_id"]),
            },
            "executado_por": str(user["id"]),
            "origem": "api_coach_athlete_onboarding_v1",
        })

        return {
            "status": "convite_enviado",
            "pessoa_id": person_id,
            "participante_id": participant_id,
            "perfil_esportivo_id": str(profile["id"]),
            "conta_id": str(linked["id"]),
            "email": email,
            "projeto_id": str(projeto_id),
            "tecnico_responsavel_pessoa_id": str(actor["pessoa_id"]),
            "escopo_profissional": scope,
            "proxima_etapa": "atleta_aceitar_convite_e_completar_onboarding",
        }
    except HTTPException:
        # A pessoa é preservada para auditoria apenas se alguma etapa posterior já existiu.
        # Como o fluxo é transacional por aplicação, limpamos os vínculos parciais mais óbvios.
        for table in ("agp_participantes_projeto", "agp_perfis_esportivos", "agp_contas_acesso", "agp_papeis_institucionais"):
            try:
                _request("DELETE", f"/rest/v1/{table}", params={"pessoa_id": f"eq.{person_id}"})
            except Exception:
                pass
        try:
            _request("DELETE", "/rest/v1/agp_pessoas", params={"id": f"eq.{person_id}"})
        except Exception:
            pass
        raise
