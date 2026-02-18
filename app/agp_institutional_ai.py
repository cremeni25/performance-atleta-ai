import numpy as np
import requests
from app.supabase_client import SUPABASE_URL, HEADERS


def buscar_scores_clube(clube_id):

    url = f"{SUPABASE_URL}/rest/v1/perfis_atletas?clube_id=eq.{clube_id}&select=id"

    atletas = requests.get(url, headers=HEADERS).json()

    ids = [a["id"] for a in atletas]

    if not ids:
        return []

    id_filter = ",".join(ids)

    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=in.({id_filter})"

    return requests.get(url, headers=HEADERS).json()


def calcular_indicadores(scores):

    if not scores:
        return None

    valores = [s["score_global"] for s in scores]

    media = np.mean(valores)

    risco = sum(1 for v in valores if v < 60) / len(valores) * 100

    return {
        "media_clube": round(media, 2),
        "percentual_risco": round(risco, 2)
    }


def gerar_diagnostico_institucional(media):

    if media < 60:
        return "Equipe apresenta desempenho geral abaixo do ideal."
    elif media < 75:
        return "Equipe em nível competitivo com potencial de evolução."
    else:
        return "Equipe apresenta alto nível de performance coletiva."
