# =========================================================
# main.py
# Servidor Backend - Algoritmo Performance Atleta
# =========================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# =========================================================
# CRIAÇÃO DA APLICAÇÃO
# =========================================================

app = FastAPI(
    title="Performance Atleta API",
    description="API do sistema de análise integral de atletas",
    version="1.0.0"
)


# =========================================================
# CONFIGURAÇÃO CORS (IMPORTANTE PARA APP FUTURO)
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # depois vamos restringir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ENDPOINT BÁSICO DE SAÚDE DO SISTEMA
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
# IMPORTANTE:
# Não colocar lógica aqui.
# Este arquivo apenas inicia a API.
# =========================================================
