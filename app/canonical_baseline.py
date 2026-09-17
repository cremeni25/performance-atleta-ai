from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.identity_context import _authenticated_user
from app.participant_onboarding import _request
from app.canonical_longitudinal_intelligence import _actor_person, _target_participant

router = APIRouter(prefix="/api/v1", tags=["canonical-baseline"])

BASELINE_COMPETENCIES = {
    "swimming.coaching",
    "strength_conditioning",
    "physiology.exercise",
    "medicine.clinical",
    "performance.analysis",
}
BASELINE_CAPABILITIES = {
    "training.plan",
    "training.record",
    "assessment.physical",
    "assessment.physiology",
    "assessment.medical",
    "analysis.performance",
    "evidence.review_technical",
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
        "select": "papel_codigo,capacidades,competencias",
    }))


def _authorize_baseline(actor_pessoa_id: str, participant: dict[str, Any]) -> dict[str, Any]:
    contexts = _contexts(actor_pessoa_id, str(participant.get("projeto_id") or ""))
    for context in contexts:
        caps = {
            item.get("codigo") for item in (context.get("capacidades") or [])
            if isinstance(item, dict) and item.get("codigo")
        }
        if "platform.govern" in caps:
            continue
        if not caps.intersection(BASELINE_CAPABILITIES):
            continue
        for competence in (context.get("competencias") or []):
            if not isinstance(competence, dict):
                continue
            code = competence.get("codigo")
            if code not in BASELINE_COMPETENCIES:
                continue
            requires = bool(competence.get("requer_credencial_regulada"))
            verified = bool(competence.get("credencial_verificada"))
            if requires and not verified:
                continue
            return {
                "papel_codigo": context.get("papel_codigo"),
                "competencia_codigo": code,
                "requer_credencial": requires,
                "credencial_verificada": verified,
            }
    raise HTTPException(status_code=403, detail="Papel/competência insuficiente para registrar linha de base")


def _person(pessoa_id: str) -> dict[str, Any]:
    row = _first(_request("GET", "/rest/v1/agp_pessoas", params={
        "id": f"eq.{pessoa_id}", "select": "id,data_nascimento,status", "limit": "1",
    }))
    if not row:
        raise HTTPException(status_code=422, detail="Pessoa canônica não encontrada")
    if not row.get("data_nascimento"):
        raise HTTPException(status_code=422, detail="Data de nascimento é obrigatória para idade cronológica precisa")
    return row


def _legacy_athlete_id(pessoa_id: str) -> str | None:
    profile = _first(_request("GET", "/rest/v1/agp_perfis_esportivos", params={
        "pessoa_id": f"eq.{pessoa_id}", "status": "eq.ativo",
        "select": "legacy_perfil_atleta_id", "limit": "1",
    }))
    return str(profile["legacy_perfil_atleta_id"]) if profile and profile.get("legacy_perfil_atleta_id") else None


def _decimal_age(birth: date, reference: date) -> float:
    if reference < birth:
        raise HTTPException(status_code=422, detail="Data de referência anterior à data de nascimento")
    return round((reference - birth).days / 365.2425, 6)


def _maturation(age: float, sex: str, standing: float, sitting: float | None, mass: float) -> dict[str, Any]:
    if sitting is None:
        return {
            "metodo_maturacional": None,
            "versao_maturacao": None,
            "offset_maturacional_anos": None,
            "idade_pico_velocidade_anos": None,
            "classificacao_maturacional": None,
            "maturacao_observacoes": "Não estimado: altura sentada não informada.",
        }
    if sitting >= standing:
        raise HTTPException(status_code=422, detail="Altura sentada deve ser menor que a altura em pé")
    leg = standing - sitting
    sx = sex.strip().lower()
    if sx == "masculino":
        offset = (-9.236 + 0.0002708 * (leg * sitting) - 0.001663 * (age * leg)
                  + 0.007216 * (age * sitting) + 0.02292 * ((mass / standing) * 100))
    elif sx == "feminino":
        offset = (-9.376 + 0.0001882 * (leg * sitting) + 0.0022 * (age * leg)
                  + 0.005841 * (age * sitting) - 0.002658 * (age * mass)
                  + 0.07693 * ((mass / standing) * 100))
    else:
        return {
            "metodo_maturacional": None,
            "versao_maturacao": None,
            "offset_maturacional_anos": None,
            "idade_pico_velocidade_anos": None,
            "classificacao_maturacional": None,
            "maturacao_observacoes": "Não estimado: a equação antropométrica disponível requer sexo de referência masculino ou feminino.",
        }
    aphv = age - offset
    classification = "pré-PHV" if offset < -1 else "circa-PHV" if offset <= 1 else "pós-PHV"
    return {
        "metodo_maturacional": "Mirwald 2002 - maturity offset antropométrico",
        "versao_maturacao": "MIRWALD-2002-AGP-1.0",
        "offset_maturacional_anos": round(offset, 6),
        "idade_pico_velocidade_anos": round(aphv, 6),
        "classificacao_maturacional": classification,
        "maturacao_observacoes": (
            "Estimativa antropométrica não invasiva. Não equivale a Tanner nem a diagnóstico clínico; "
            "deve ser interpretada considerando erro do método e maturadores precoces/tardios."
        ),
    }


class CanonicalBaselineCreate(BaseModel):
    categoria: str | None = Field(default=None, max_length=120)
    sexo_registrado: str = Field(min_length=1, max_length=40)
    modalidade: str = Field(min_length=2, max_length=120)
    prova_posicao: str | None = Field(default=None, max_length=120)
    altura_cm: float = Field(gt=30, le=260)
    massa_kg: float = Field(gt=5, le=400)
    envergadura_cm: float | None = Field(default=None, gt=30, le=300)
    altura_sentado_cm: float | None = Field(default=None, gt=30, le=220)
    data_referencia: date
    origem: str = Field(min_length=2, max_length=120)
    observacoes: str | None = Field(default=None, max_length=2000)


@router.get("/participantes/{participante_id}/linha-base-canonica")
def get_canonical_baseline(participante_id: UUID, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    if str(actor["pessoa_id"]) != str(participant["pessoa_id"]):
        contexts = _contexts(str(actor["pessoa_id"]), str(participant["projeto_id"]))
        if not contexts:
            raise HTTPException(status_code=403, detail="Sem vínculo ativo com o projeto do atleta")
    rows = _rows(_request("GET", "/rest/v1/agp_linhas_base_canonicas", params={
        "participante_id": f"eq.{participante_id}", "select": "*", "order": "data_referencia.desc", "limit": "20",
    }))
    return {
        "modelo": "AGP-Canonical-Baseline-v1",
        "participante_id": str(participante_id),
        "linhas_base": rows,
        "principio": "idade_cronologica_precisa_antes_de_estimativa_maturacional",
    }


@router.post("/participantes/{participante_id}/linha-base-canonica", status_code=status.HTTP_201_CREATED)
def create_canonical_baseline(
    participante_id: UUID,
    payload: CanonicalBaselineCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _authenticated_user(authorization)
    actor = _actor_person(str(user["id"]))
    participant = _target_participant(participante_id)
    scope = _authorize_baseline(str(actor["pessoa_id"]), participant)
    person = _person(str(participant["pessoa_id"]))
    birth = date.fromisoformat(str(person["data_nascimento"]))
    age = _decimal_age(birth, payload.data_referencia)
    maturation = _maturation(age, payload.sexo_registrado, payload.altura_cm, payload.altura_sentado_cm, payload.massa_kg)

    _request("PATCH", "/rest/v1/agp_linhas_base_atleta", params={
        "pessoa_id": f"eq.{participant['pessoa_id']}",
        "projeto_id": f"eq.{participant['projeto_id']}",
        "status": "in.(completa,validada)",
    }, payload={"status": "substituida", "updated_at": datetime.now(timezone.utc).isoformat()})

    now = datetime.now(timezone.utc).isoformat()
    created = _first(_request("POST", "/rest/v1/agp_linhas_base_atleta", payload={
        "pessoa_id": participant["pessoa_id"],
        "participante_id": participant["id"],
        "atleta_id": _legacy_athlete_id(str(participant["pessoa_id"])),
        "projeto_id": participant["projeto_id"],
        "categoria": payload.categoria,
        "idade_cronologica": age,
        "idade_calculada_em": payload.data_referencia.isoformat(),
        "idade_calculo_metodo": "dias_exatos_divididos_por_365.2425",
        "sexo_registrado": payload.sexo_registrado,
        "modalidade": payload.modalidade,
        "prova_posicao": payload.prova_posicao,
        "estagio_maturacional": maturation["classificacao_maturacional"],
        "altura_cm": payload.altura_cm,
        "massa_kg": payload.massa_kg,
        "envergadura_cm": payload.envergadura_cm,
        "altura_sentado_cm": payload.altura_sentado_cm,
        "metodo_maturacional": maturation["metodo_maturacional"],
        "versao_maturacao": maturation["versao_maturacao"],
        "offset_maturacional_anos": maturation["offset_maturacional_anos"],
        "idade_pico_velocidade_anos": maturation["idade_pico_velocidade_anos"],
        "classificacao_maturacional": maturation["classificacao_maturacional"],
        "maturacao_observacoes": maturation["maturacao_observacoes"],
        "data_referencia": payload.data_referencia.isoformat(),
        "origem": payload.origem,
        "responsavel_auth_id": str(user["id"]),
        "observacoes": payload.observacoes,
        "status": "validada",
        "completude": 100,
        "validado_por_auth_id": str(user["id"]),
        "validado_em": now,
        "competencia_codigo": scope["competencia_codigo"],
        "credencial_verificada_no_registro": scope["credencial_verificada"],
        "updated_at": now,
    }))
    if not created:
        raise HTTPException(status_code=502, detail="Falha ao registrar linha de base canônica")
    return {
        "linha_base": created,
        "idade_cronologica_exata": age,
        "escopo_profissional": scope,
        "maturacao": maturation,
        "nao_significa": ["Tanner", "diagnostico_clinico", "predicao_individual_deterministica"],
    }
