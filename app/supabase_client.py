import os
from supabase import create_client, Client


# ==============================
# CONFIGURAÇÃO SUPABASE
# ==============================

SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL não definida nas variáveis de ambiente.")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY não definida nas variáveis de ambiente.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==============================
# INSERÇÃO DE ATLETA
# ==============================

def inserir_atleta(dados: dict):
    """
    Insere um novo atleta na tabela perfis_atletas.
    """

    try:
        response = supabase.table("perfis_atletas").insert({
            "nome": dados["nome"],
            "idade": dados["idade"],
            "sexo": dados["sexo"],
            "nivel": dados["nivel"],
            "esporte_id": dados["esporte_id"],
            "modalidade_id": dados["modalidade_id"],
        }).execute()

        return response

    except Exception as e:
        raise Exception(f"Erro ao inserir atleta: {str(e)}")
