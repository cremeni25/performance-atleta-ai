# =========================================================
# main.py
# Servidor Backend - Algoritmo Performance Atleta
# =========================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.supabase_client import supabase


# =========================================================
# CRIAÇÃO DA APLICAÇÃO
# =========================================================

app = FastAPI(
    title="Performance Atleta API",
    description="API do sistema de análise integral de atletas",
    version="1.0.0"
)


# =========================================================
# CONFIGURAÇÃO CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MODELOS DE DADOS
# =========================================================

class PerfilAtletaCreate(BaseModel):
    nome: str
    idade: int
    sexo: str
    nivel: str
    esporte_id: str
    modalidade_id: str


# =========================================================
# ENDPOINTS BÁSICOS
# =========================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "sistema": "Performance Atleta",
        "versao": "1.0"
    }


@app.get("/health")
def health_check():
    return {"health": "ok"}


# =========================================================
# ENDPOINT CADASTRO DE ATLETA
# =========================================================

@app.post("/atletas")
def criar_atleta(perfil: PerfilAtletaCreate):

    data = {
        "nome": perfil.nome,
        "idade": perfil.idade,
        "sexo": perfil.sexo,
        "nivel": perfil.nivel,
        "esporte_id": perfil.esporte_id,
        "modalidade_id": perfil.modalidade_id
    }

    response = supabase.table("perfis_atletas").insert(data).execute()

    return {
        "status": "atleta_criado",
        "dados": response.data
    }


# =========================================================
# OBSERVAÇÃO ARQUITETURAL
# =========================================================
# Este arquivo apenas inicia a API e define endpoints.
# Lógica algorítmica ficará em módulos separados.
# =========================================================
