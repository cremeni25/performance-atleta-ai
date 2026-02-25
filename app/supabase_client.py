import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL não definida.")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY não definida.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def inserir_atleta(dados: dict):
    url = f"{SUPABASE_URL}/rest/v1/perfis_atletas"

    payload = {
        "nome": dados["nome"],
        "idade": dados["idade"],
        "sexo": dados["sexo"],
        "nivel": dados["nivel"],
        "esporte_id": dados["esporte_id"],
        "modalidade_id": dados["modalidade_id"]
    }

    response = requests.post(url, json=payload, headers=HEADERS)

    if response.status_code >= 400:
        raise Exception(f"Erro Supabase: {response.text}")

    return response.json()
