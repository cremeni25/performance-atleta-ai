import requests
from app.supabase_client import SUPABASE_URL, HEADERS


def salvar_score_atleta(dados_score: dict):

    url = f"{SUPABASE_URL}/rest/v1/score_atleta"

    response = requests.post(
        url,
        json=dados_score,
        headers=HEADERS
    )

    return response.json()
