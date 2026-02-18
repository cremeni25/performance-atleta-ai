from datetime import date
import requests
from app.supabase_client import SUPABASE_URL, HEADERS


def gerar_alerta(atleta_id, tipo_alerta, descricao):

    url = f"{SUPABASE_URL}/rest/v1/alertas_algoritmo"

    payload = {
        "atleta_id": atleta_id,
        "tipo_alerta": tipo_alerta,
        "descricao": descricao,
        "data_emissao": str(date.today()),
        "status": "ativo"
    }

    requests.post(url, json=payload, headers=HEADERS)


def gerar_plano_acao(atleta_id, recomendacao):

    url = f"{SUPABASE_URL}/rest/v1/plano_acao_atleta"

    payload = {
        "atleta_id": atleta_id,
        "tipo_meta": "intervencao_automatica",
        "descricao_meta": recomendacao,
        "status_meta": "pendente",
        "data_criacao": str(date.today())
    }

    requests.post(url, json=payload, headers=HEADERS)


def avaliar_intervencao(atleta_id, tendencia, risco):

    if risco:
        gerar_alerta(
            atleta_id,
            "risco_performance",
            "Queda contínua detectada. Intervenção imediata recomendada."
        )

        gerar_plano_acao(
            atleta_id,
            "Reduzir carga de treino e reavaliar indicadores fisiológicos."
        )

    elif tendencia == "Queda de performance":
        gerar_alerta(
            atleta_id,
            "queda_desempenho",
            "Tendência negativa identificada."
        )

        gerar_plano_acao(
            atleta_id,
            "Revisar planejamento técnico e psicológico."
        )

    elif tendencia == "Estabilidade":
        gerar_plano_acao(
            atleta_id,
            "Implementar estímulos progressivos para evitar estagnação."
        )
