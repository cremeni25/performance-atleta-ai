# ==========================================================
# AGP CORE ENGINE v2
# Algoritmo Global de Performance do Atleta
# Versão Científica Multidimensional Profissional
# ==========================================================

import numpy as np
from datetime import date


class Athlete:

    def __init__(self, profile, normalized_data, history=None):
        self.profile = profile
        self.normalized_data = normalized_data
        self.history = history if history else []

        self.dimension_scores = {}
        self.score_global = 0
        self.classificacao = ""
        self.diagnostico = ""


# ==========================================================
# ENGINE CIENTÍFICO
# ==========================================================

class GlobalPerformanceEngine:

    BASE_WEIGHTS = {
        "fisiologico": 0.25,
        "tecnico": 0.20,
        "recuperacao": 0.20,
        "mental": 0.15,
        "fisico": 0.10,
        "contextual": 0.10
    }

    # ------------------------------------------------------

    def calcular_dimensoes(self, athlete):

        for dim, valores in athlete.normalized_data.items():
            athlete.dimension_scores[dim] = float(np.mean(valores))

    # ------------------------------------------------------

    def aplicar_pesos_adaptativos(self, athlete):

        weights = self.BASE_WEIGHTS.copy()

        idade = athlete.profile.get("idade", 18)
        nivel = athlete.profile.get("nivel", "base")

        # Ajustes por idade
        if idade < 18:
            weights["fisiologico"] *= 1.1
            weights["mental"] *= 0.9

        # Ajustes por nível competitivo
        if nivel.lower() == "elite":
            weights["tecnico"] *= 1.2
            weights["recuperacao"] *= 1.2

        # Normalizar pesos
        total = sum(weights.values())
        for k in weights:
            weights[k] /= total

        return weights

    # ------------------------------------------------------

    def calcular_score_global(self, athlete, weights):

        score = 0

        for dim, peso in weights.items():
            valor = athlete.dimension_scores.get(dim, 0)
            score += valor * peso

        athlete.score_global = round(score, 2)

    # ------------------------------------------------------

    def classificar(self, athlete):

        score = athlete.score_global

        if score < 40:
            athlete.classificacao = "Crítico"
        elif score < 60:
            athlete.classificacao = "Desenvolvimento"
        elif score < 75:
            athlete.classificacao = "Competitivo"
        elif score < 90:
            athlete.classificacao = "Alto Rendimento"
        else:
            athlete.classificacao = "Elite Mundial"

    # ------------------------------------------------------

    def gerar_diagnostico(self, athlete):

        pontos_fracos = []
        pontos_fortes = []

        for dim, valor in athlete.dimension_scores.items():
            if valor < 60:
                pontos_fracos.append(dim)
            elif valor > 80:
                pontos_fortes.append(dim)

        diagnostico = f"Classificação geral: {athlete.classificacao}. "

        if pontos_fortes:
            diagnostico += f"Pontos fortes identificados em {', '.join(pontos_fortes)}. "

        if pontos_fracos:
            diagnostico += f"Atenção necessária em {', '.join(pontos_fracos)}. "

        if not pontos_fracos:
            diagnostico += "Perfil equilibrado e estável."

        athlete.diagnostico = diagnostico

    # ------------------------------------------------------

    def run(self, athlete):

        self.calcular_dimensoes(athlete)

        weights = self.aplicar_pesos_adaptativos(athlete)

        self.calcular_score_global(athlete, weights)

        self.classificar(athlete)

        self.gerar_diagnostico(athlete)

        return {
            "score_fisico": athlete.dimension_scores.get("fisico"),
            "score_fisiologico": athlete.dimension_scores.get("fisiologico"),
            "score_tecnico": athlete.dimension_scores.get("tecnico"),
            "score_mental": athlete.dimension_scores.get("mental"),
            "score_recuperacao": athlete.dimension_scores.get("recuperacao"),
            "score_global": athlete.score_global,
            "nivel_classificacao": athlete.classificacao,
            "diagnostico": athlete.diagnostico,
            "data_calculo": str(date.today())
        }
