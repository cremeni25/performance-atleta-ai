"""Inicialização segura do pacote AGP.

O bootstrap abaixo é idempotente: em cada inicialização do backend ele confere
se o usuário proprietário já está vinculado ao perfil Master e corrige apenas
quando necessário. Falhas são registradas sem impedir a API de subir.
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


def bootstrap_master_owner() -> None:
    """Vincula o proprietário ao perfil Master sem duplicar registros."""

    if _headers() is None:
        LOGGER.warning("Bootstrap Master ignorado: ambiente Supabase incompleto")
        return

    try:
        profile = _existing_profile()

        # O frontend atual aceita `tipo_usuario` ou `funcao`. Como instalações
        # antigas podem ter apenas uma dessas colunas, tentamos variações seguras.
        variants = [
            {
                "tipo_usuario": "master",
                "funcao": "master",
                "email": OWNER_EMAIL,
            },
            {"tipo_usuario": "master", "email": OWNER_EMAIL},
            {"funcao": "master", "email": OWNER_EMAIL},
            {"tipo_usuario": "master"},
            {"funcao": "master"},
        ]

        if profile:
            current = str(profile.get("tipo_usuario") or profile.get("funcao") or "").lower()
            if current == "master":
                LOGGER.info("Master Owner já configurado para %s", OWNER_EMAIL)
                return

            for payload in variants:
                if _patch_profile(payload):
                    LOGGER.info("Master Owner atualizado com sucesso para %s", OWNER_EMAIL)
                    return

            raise RuntimeError("Nenhuma estrutura compatível permitiu atualizar o perfil")

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
                LOGGER.info("Master Owner criado com sucesso para %s", OWNER_EMAIL)
                return

        raise RuntimeError(
            "Perfil inexistente e tabela exige campos adicionais; bootstrap não alterou dados"
        )
    except Exception as exc:  # não derruba a API por falha administrativa
        LOGGER.exception("Falha controlada no bootstrap Master Owner: %s", exc)


bootstrap_master_owner()
