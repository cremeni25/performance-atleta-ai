"""Inicialização segura do pacote AGP.

O bootstrap é idempotente: confere o vínculo do proprietário e, somente enquanto
o primeiro acesso não tiver sido provisionado, define uma senha temporária única.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

LOGGER = logging.getLogger("agp.master_bootstrap")

OWNER_EMAIL = os.getenv("AGP_OWNER_EMAIL", "anderson@cremeni.com.br")
OWNER_AUTH_ID = os.getenv(
    "AGP_OWNER_AUTH_ID",
    "14737212-032c-4b69-a6cb-a6fe80e8cf11",
)
TEMPORARY_MASTER_PASSWORD = "Agp!3hgjtlAGgJr2MOEawQypx51T"


def _headers() -> dict[str, str] | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    headers = _headers()
    if headers is None:
        raise RuntimeError("Credenciais do Supabase indisponíveis")
    return requests.request(
        method,
        f"{base_url}{path}",
        headers=headers,
        timeout=15,
        **kwargs,
    )


def _existing_profile() -> dict[str, Any] | None:
    response = _request(
        "GET",
        f"/rest/v1/perfis_atletas?auth_id=eq.{OWNER_AUTH_ID}&select=*",
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao consultar perfil: {response.text}")
    rows = response.json()
    return rows[0] if rows else None


def _patch_profile(payload: dict[str, Any]) -> bool:
    response = _request(
        "PATCH",
        f"/rest/v1/perfis_atletas?auth_id=eq.{OWNER_AUTH_ID}",
        data=json.dumps(payload),
    )
    return response.status_code < 400


def _insert_profile(payload: dict[str, Any]) -> bool:
    response = _request(
        "POST",
        "/rest/v1/perfis_atletas",
        data=json.dumps(payload),
    )
    return response.status_code < 400


def _provision_temporary_password() -> None:
    user_path = f"/auth/v1/admin/users/{OWNER_AUTH_ID}"
    current = _request("GET", user_path)
    if current.status_code >= 400:
        raise RuntimeError(f"Falha ao consultar usuário Auth: {current.text}")

    user = current.json()
    metadata = user.get("user_metadata") or {}
    if metadata.get("agp_initial_password_issued") is True:
        LOGGER.info("Senha inicial do Master já foi provisionada")
        return

    metadata.update(
        {
            "agp_initial_password_issued": True,
            "tipo_usuario": "master",
            "is_owner": True,
        }
    )
    response = _request(
        "PUT",
        user_path,
        data=json.dumps(
            {
                "password": TEMPORARY_MASTER_PASSWORD,
                "email_confirm": True,
                "user_metadata": metadata,
            }
        ),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao provisionar senha inicial: {response.text}")
    LOGGER.info("Senha temporária do Master provisionada com sucesso")


def bootstrap_master_owner() -> None:
    """Vincula o proprietário ao perfil Master sem duplicar registros."""

    if _headers() is None:
        LOGGER.warning("Bootstrap Master ignorado: ambiente Supabase incompleto")
        return

    try:
        profile = _existing_profile()
        variants = [
            {"tipo_usuario": "master", "funcao": "master", "email": OWNER_EMAIL},
            {"tipo_usuario": "master", "email": OWNER_EMAIL},
            {"funcao": "master", "email": OWNER_EMAIL},
            {"tipo_usuario": "master"},
            {"funcao": "master"},
        ]

        if profile:
            current = str(profile.get("tipo_usuario") or profile.get("funcao") or "").lower()
            if current != "master":
                for payload in variants:
                    if _patch_profile(payload):
                        break
                else:
                    raise RuntimeError("Nenhuma estrutura compatível permitiu atualizar o perfil")
        else:
            insert_variants = [
                {
                    "auth_id": OWNER_AUTH_ID,
                    "email": OWNER_EMAIL,
                    "nome": "Anderson Navarro",
                    "tipo_usuario": "master",
                    "funcao": "master",
                },
                {
                    "auth_id": OWNER_AUTH_ID,
                    "email": OWNER_EMAIL,
                    "nome": "Anderson Navarro",
                    "tipo_usuario": "master",
                },
                {
                    "auth_id": OWNER_AUTH_ID,
                    "email": OWNER_EMAIL,
                    "nome": "Anderson Navarro",
                    "funcao": "master",
                },
            ]
            for payload in insert_variants:
                if _insert_profile(payload):
                    break
            else:
                raise RuntimeError("Não foi possível criar o perfil Master")

        _provision_temporary_password()
    except Exception as exc:
        LOGGER.exception("Falha controlada no bootstrap Master Owner: %s", exc)


bootstrap_master_owner()
