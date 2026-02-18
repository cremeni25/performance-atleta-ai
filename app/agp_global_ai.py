import numpy as np
import requests
from app.supabase_client import SUPABASE_URL, HEADERS


def buscar_todos_clubes():
    url = f"{SUPABASE_URL}/rest/v1/clubes"
    return requests.get(url, headers=HEADERS).json()


def buscar_scores_por_clube(clube_id):

    url = f"{SUPABASE_URL}/rest/v1/perfis_atletas?clube_id=eq.{clube_id}&select=id"
    atletas = requests.get(url, headers=HEADERS).json()

    ids = [a["id"] for a in atletas]
    if not ids:
        return []

    filtro = ",".join(ids)
    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=in.({filtro})"

    return requests.get(url, headers=HEADERS).json()


def calcular_media_clube(scores):
    if not scores:
        return None
    valores = [s["score_global"] for s in scores]
    return np.mean(valores)


def gerar_ranking_global():

    clubes = buscar_todos_clubes()
    ranking = []

    for clube in clubes:
        scores = buscar_scores_por_clube(clube["id"])
        media = calcular_media_clube(scores)

        if media:
            ranking.append({
                "clube_id": clube["id"],
                "nome_clube": clube["nome"],
                "media_performance": round(media, 2)
            })

    ranking.sort(key=lambda x: x["media_performance"], reverse=True)

    return ranking


def calcular_indicadores_globais():

    url = f"{SUPABASE_URL}/rest/v1/score_atleta"
    scores = requests.get(url, headers=HEADERS).json()

    if not scores:
        return None

    valores = [s["score_global"] for s in scores]

    media_global = np.mean(valores)
    risco_global = sum(1 for v in valores if v < 60) / len(valores) * 100

    return {
        "media_global": round(media_global, 2),
        "percentual_risco_global": round(risco_global, 2)
    }
