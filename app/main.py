from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os

from app.supabase_client import inserir_atleta, supabase
from app.score_atleta_repository import salvar_score_atleta
from app.agp_core_engine import Athlete, GlobalPerformanceEngine

from app.agp_longitudinal_ai import analisar_tendencia, detectar_risco, prever_nivel
from app.agp_intervention_ai import avaliar_intervencao
from app.agp_institutional_ai import buscar_scores_clube, calcular_indicadores, gerar_diagnostico_institucional
from app.agp_global_ai import gerar_ranking_global, calcular_indicadores_globais


app = FastAPI()

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG SUPABASE
# =========================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# =========================
# MODELOS
# =========================

class PerfilAtletaCreate(BaseModel):
    nome: str
    idade: int
    sexo: str
    nivel: str
    esporte_id: str
    modalidade_id: str


class DadosAnalise(BaseModel):
    idade: int
    nivel: str

    fisiologica: list[float]
    tecnica: list[float]
    recuperacao: list[float]
    psicologica: list[float]
    fisica: list[float]
    contextual: list[float]


class DadosAnaliseVinculada(DadosAnalise):
    atleta_id: str


# =========================
# STATUS API
# =========================

@app.get("/")
def root():
    return {"status": "AGP Backend Online"}

# =========================
# CRIAR ATLETA
# =========================

@app.post("/atletas")
def criar_atleta(perfil: PerfilAtletaCreate):

    data = perfil.dict()
    resultado = inserir_atleta(data)

    return {
        "status": "atleta_criado",
        "dados": resultado
    }

# =========================
# DASHBOARD DO ATLETA
# =========================

@app.get("/athlete/dashboard/{auth_id}")
def dashboard_atleta(auth_id: str):

    perfil = supabase.table("perfis_atletas") \
        .select("*") \
        .eq("auth_id", auth_id) \
        .maybe_single() \
        .execute()

    if not perfil.data:
        raise HTTPException(status_code=404, detail="Perfil do atleta não encontrado")

    atleta_id = perfil.data["id"]

    score = supabase.table("score_atleta") \
        .select("*") \
        .eq("atleta_id", atleta_id) \
        .order("data_calculo", desc=True) \
        .limit(1) \
        .execute()

    carga = supabase.table("carga_treinamento_atleta") \
        .select("*") \
        .eq("atleta_id", atleta_id) \
        .order("data", desc=True) \
        .limit(7) \
        .execute()

    sono = supabase.table("sono_atleta") \
        .select("*") \
        .eq("atleta_id", atleta_id) \
        .order("data", desc=True) \
        .limit(7) \
        .execute()

    return {
        "perfil": perfil.data,
        "score": score.data,
        "carga": carga.data,
        "sono": sono.data
    }

# =========================
# ANALISE CORE ENGINE
# =========================

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

# =========================
# ANALISE + SALVAR SCORE
# =========================

@app.post("/analisar-e-salvar-atleta-vinculado")
def analisar_e_salvar_atleta_vinculado(dados: DadosAnaliseVinculada):

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

    dados_para_salvar = {
        "atleta_id": dados.atleta_id,
        "score_fisico": resultado["score_fisico"],
        "score_fisiologico": resultado["score_fisiologico"],
        "score_tecnico": resultado["score_tecnico"],
        "score_mental": resultado["score_mental"],
        "score_recuperacao": resultado["score_recuperacao"],
        "score_global": resultado["score_global"],
        "nivel_classificacao": resultado["nivel_classificacao"],
        "diagnostico": resultado["diagnostico"],
        "data_calculo": resultado["data_calculo"]
    }

    salvar_score_atleta(dados_para_salvar)

    return {
        "status": "score_vinculado_salvo",
        "resultado": resultado
    }

# =========================
# ANALISE LONGITUDINAL
# =========================

@app.get("/analise-longitudinal/{atleta_id}")
def analise_longitudinal(atleta_id: str):

    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=eq.{atleta_id}&order=data_calculo.asc"

    response = requests.get(url, headers=HEADERS)
    dados = response.json()

    if not dados:
        return {"mensagem": "Sem histórico suficiente"}

    scores = [d["score_global"] for d in dados]

    tendencia = analisar_tendencia(scores)
    risco = detectar_risco(scores)
    previsao = prever_nivel(scores[-1])

    return {
        "tendencia": tendencia,
        "risco": risco,
        "previsao": previsao,
        "historico_scores": scores
    }

# =========================
# BENCHMARK GLOBAL
# =========================

@app.get("/benchmark-global")
def benchmark_global():

    ranking = gerar_ranking_global()
    indicadores = calcular_indicadores_globais()

    return {
        "ranking_global_clubes": ranking,
        "indicadores_globais": indicadores
    }
