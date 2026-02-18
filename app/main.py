from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.supabase_client import inserir_atleta


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PerfilAtletaCreate(BaseModel):
    nome: str
    idade: int
    sexo: str
    nivel: str
    esporte_id: str
    modalidade_id: str


@app.get("/")
def root():
    return {"status": "online"}


@app.post("/atletas")
def criar_atleta(perfil: PerfilAtletaCreate):

    data = perfil.dict()
    resultado = inserir_atleta(data)

    return {
        "status": "atleta_criado",
        "dados": resultado
    }

# =====================================================
# INTEGRAÇÃO AGP CORE ENGINE — ANÁLISE DE PERFORMANCE
# =====================================================

from app.agp_core_engine import Athlete, GlobalPerformanceEngine

class DadosAnalise(BaseModel):
    idade: int
    nivel: str

    # Dados simulados das dimensões (0–100)
    fisiologica: list[float]
    tecnica: list[float]
    recuperacao: list[float]
    psicologica: list[float]
    fisica: list[float]
    contextual: list[float]

@app.post("/analisar-atleta")
def analisar_atleta(dados: DadosAnalise):

    # Perfil do atleta
    profile = {
        "idade": dados.idade,
        "nivel": dados.nivel
    }

    # Dados estruturados para o motor
    normalized_data = {
        "fisiologica": dados.fisiologica,
        "tecnica": dados.tecnica,
        "recuperacao": dados.recuperacao,
        "psicologica": dados.psicologica,
        "fisica": dados.fisica,
        "contextual": dados.contextual
    }

    atleta = Athlete(profile=profile, data={}, history=[])
    atleta.normalized_data = normalized_data

    engine = GlobalPerformanceEngine()
    resultado = engine.run(atleta)

    return {
        "score_cientifico": resultado.scientific_score,
        "score_adaptativo": resultado.adaptive_score,
        "score_final": resultado.final_score
    }

# =====================================================
# AGP CORE ENGINE V2 — ENDPOINT PROFISSIONAL
# =====================================================

@app.post("/analisar-atleta-v2")
def analisar_atleta_v2(dados: DadosAnalise):

    profile = {
        "idade": dados.idade,
        "nivel": dados.nivel
    }

    normalized_data = {
        "fisiologico": dados.fisiologica,
        "tecnico": dados.tecnica,
        "recuperacao": dados.recuperacao,
        "mental": dados.psicologica,
        "fisico": dados.fisica,
        "contextual": dados.contextual
    }

    atleta = Athlete(profile=profile, normalized_data=normalized_data)

    engine = GlobalPerformanceEngine()
    resultado = engine.run(atleta)

    return resultado
