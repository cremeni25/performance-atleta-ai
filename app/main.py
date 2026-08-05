# main.py

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from app.supabase_client import inserir_atleta, HEADERS, SUPABASE_URL
from app.score_atleta_repository import salvar_score_atleta
from app.agp_core_engine import Athlete, GlobalPerformanceEngine
from app.agp_longitudinal_ai import analisar_tendencia, detectar_risco, prever_nivel
from app.agp_intervention_ai import avaliar_intervencao
from app.agp_institutional_ai import buscar_scores_clube, calcular_indicadores, gerar_diagnostico_institucional
from app.agp_global_ai import gerar_ranking_global, calcular_indicadores_globais
from app.owner_activation import ensure_owner_profile, router as owner_activation_router
from app.participant_onboarding import router as participant_onboarding_router
from app.consent_management import router as consent_management_router

LOGGER = logging.getLogger("agp.startup")

app = FastAPI()
app.include_router(owner_activation_router)
app.include_router(participant_onboarding_router)
app.include_router(consent_management_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def repair_owner_profile_on_startup():
    try:
        result = ensure_owner_profile()
        LOGGER.info("Perfil proprietário validado: %s", result)
    except Exception as exc:
        LOGGER.exception("Falha controlada ao validar perfil proprietário: %s", exc)


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


@app.get("/")
def root():
    return {"status": "AGP Backend Online"}


@app.post("/atletas")
def criar_atleta(perfil: PerfilAtletaCreate):
    data = perfil.dict()
    resultado = inserir_atleta(data)
    return {"status": "atleta_criado", "dados": resultado}


@app.get("/athlete/dashboard/{auth_id}")
def dashboard_atleta(auth_id: str):
    url = f"{SUPABASE_URL}/rest/v1/perfis_atletas?auth_id=eq.{auth_id}&select=*"
    response = requests.get(url, headers=HEADERS)
    perfil = response.json()
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil do atleta não encontrado")

    atleta_id = perfil[0]["id"]
    score_url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=eq.{atleta_id}&order=data_calculo.desc&limit=1"
    score = requests.get(score_url, headers=HEADERS).json()
    carga_url = f"{SUPABASE_URL}/rest/v1/carga_treinamento_atleta?atleta_id=eq.{atleta_id}&order=data_treino.desc&limit=7"
    carga = requests.get(carga_url, headers=HEADERS).json()
    sono_url = f"{SUPABASE_URL}/rest/v1/sono_atleta?atleta_id=eq.{atleta_id}&order=data_registro.desc&limit=7"
    sono = requests.get(sono_url, headers=HEADERS).json()
    return {"perfil": perfil[0], "score": score, "carga": carga, "sono": sono}


@app.post("/analisar-atleta-v2")
def analisar_atleta_v2(dados: DadosAnalise):
    profile = {"idade": dados.idade, "nivel": dados.nivel}
    normalized_data = {
        "fisiologico": dados.fisiologica,
        "tecnico": dados.tecnica,
        "recuperacao": dados.recuperacao,
        "mental": dados.psicologica,
        "fisico": dados.fisica,
        "contextual": dados.contextual,
    }
    atleta = Athlete(profile=profile, normalized_data=normalized_data)
    return GlobalPerformanceEngine().run(atleta)


@app.post("/analisar-e-salvar-atleta-vinculado")
def analisar_e_salvar_atleta_vinculado(dados: DadosAnaliseVinculada):
    profile = {"idade": dados.idade, "nivel": dados.nivel}
    normalized_data = {
        "fisiologico": dados.fisiologica,
        "tecnico": dados.tecnica,
        "recuperacao": dados.recuperacao,
        "mental": dados.psicologica,
        "fisico": dados.fisica,
        "contextual": dados.contextual,
    }
    atleta = Athlete(profile=profile, normalized_data=normalized_data)
    resultado = GlobalPerformanceEngine().run(atleta)
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
        "data_calculo": resultado["data_calculo"],
    }
    salvar_score_atleta(dados_para_salvar)
    return {"status": "score_vinculado_salvo", "resultado": resultado}


@app.get("/analise-longitudinal/{atleta_id}")
def analise_longitudinal(atleta_id: str):
    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=eq.{atleta_id}&order=data_calculo.asc"
    dados = requests.get(url, headers=HEADERS).json()
    if not dados:
        return {"mensagem": "Sem histórico suficiente"}
    scores = [d["score_global"] for d in dados]
    return {
        "tendencia": analisar_tendencia(scores),
        "risco": detectar_risco(scores),
        "previsao": prever_nivel(scores[-1]),
        "historico_scores": scores,
    }


@app.post("/avaliar-intervencao/{atleta_id}")
def avaliar_intervencao_endpoint(atleta_id: str):
    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=eq.{atleta_id}&order=data_calculo.asc"
    dados = requests.get(url, headers=HEADERS).json()
    if not dados or len(dados) < 3:
        return {"mensagem": "Histórico insuficiente para intervenção"}
    scores = [d["score_global"] for d in dados]
    tendencia = analisar_tendencia(scores)
    risco = detectar_risco(scores)
    avaliar_intervencao(atleta_id, tendencia, risco)
    return {"tendencia": tendencia, "risco": risco, "intervencao_executada": True}


@app.get("/analise-institucional/{clube_id}")
def analise_institucional(clube_id: str):
    scores = buscar_scores_clube(clube_id)
    if not scores:
        return {"mensagem": "Sem dados suficientes"}
    indicadores = calcular_indicadores(scores)
    diagnostico = gerar_diagnostico_institucional(indicadores["media_clube"])
    ranking = sorted(scores, key=lambda x: x["score_global"], reverse=True)[:10]
    return {"indicadores": indicadores, "diagnostico": diagnostico, "ranking_top_10": ranking}


@app.get("/benchmark-global")
def benchmark_global():
    return {
        "ranking_global_clubes": gerar_ranking_global(),
        "indicadores_globais": calcular_indicadores_globais(),
    }
