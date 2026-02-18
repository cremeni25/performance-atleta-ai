from app.supabase_client import supabase


def salvar_score_atleta(dados_score: dict):
    response = supabase.table("score_atleta").insert(dados_score).execute()
    return response.data
