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

# =====================================================
# AGP CORE ENGINE V2 — ANÁLISE + PERSISTÊNCIA
# =====================================================

from app.score_atleta_repository import salvar_score_atleta


@app.post("/analisar-e-salvar-atleta")
def analisar_e_salvar_atleta(dados: DadosAnalise):

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
        "status": "salvo_com_sucesso",
        "resultado": resultado
    }

# =====================================================
# AGP CORE ENGINE V2 — ANÁLISE + VINCULAÇÃO AO ATLETA
# =====================================================

class DadosAnaliseVinculada(DadosAnalise):
    atleta_id: str


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

# =====================================================
# IA LONGITUDINAL — ANÁLISE HISTÓRICA DO ATLETA
# =====================================================

from app.agp_longitudinal_ai import analisar_tendencia, detectar_risco, prever_nivel


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

# =====================================================
# IA DE INTERVENÇÃO AUTOMÁTICA
# =====================================================

from app.agp_intervention_ai import avaliar_intervencao


@app.post("/avaliar-intervencao/{atleta_id}")
def avaliar_intervencao_endpoint(atleta_id: str):

    url = f"{SUPABASE_URL}/rest/v1/score_atleta?atleta_id=eq.{atleta_id}&order=data_calculo.asc"

    response = requests.get(url, headers=HEADERS)
    dados = response.json()

    if not dados or len(dados) < 3:
        return {"mensagem": "Histórico insuficiente para intervenção"}

    scores = [d["score_global"] for d in dados]

    from app.agp_longitudinal_ai import analisar_tendencia, detectar_risco

    tendencia = analisar_tendencia(scores)
    risco = detectar_risco(scores)

    avaliar_intervencao(atleta_id, tendencia, risco)

    return {
        "tendencia": tendencia,
        "risco": risco,
        "intervencao_executada": True
    }

# =====================================================
# IA INSTITUCIONAL — ANÁLISE DO CLUBE
# =====================================================

from app.agp_institutional_ai import buscar_scores_clube, calcular_indicadores, gerar_diagnostico_institucional


@app.get("/analise-institucional/{clube_id}")
def analise_institucional(clube_id: str):

    scores = buscar_scores_clube(clube_id)

    if not scores:
        return {"mensagem": "Sem dados suficientes"}

    indicadores = calcular_indicadores(scores)

    diagnostico = gerar_diagnostico_institucional(indicadores["media_clube"])

    ranking = sorted(scores, key=lambda x: x["score_global"], reverse=True)[:10]

    return {
        "indicadores": indicadores,
        "diagnostico": diagnostico,
        "ranking_top_10": ranking
    }
