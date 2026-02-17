# =========================================================
# estado_atleta.py
# Núcleo Computacional do Estado do Atleta
# =========================================================

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EstadoGlobal(Enum):
    PICO_FUNCIONAL = "PICO_FUNCIONAL"
    ADAPTANDO = "ADAPTANDO"
    ESTAVEL = "ESTAVEL"
    EM_ALERTA = "EM_ALERTA"
    EM_RISCO = "EM_RISCO"


def normalizar_score(valor: float) -> float:
    return max(0.0, min(100.0, valor))


@dataclass
class EstadoAtleta:
    fisico: float
    psicologico: float
    fisiologico: float
    nutricional: float
    adaptativo: float
    timestamp: datetime = datetime.now()

    def __post_init__(self):
        self.fisico = normalizar_score(self.fisico)
        self.psicologico = normalizar_score(self.psicologico)
        self.fisiologico = normalizar_score(self.fisiologico)
        self.nutricional = normalizar_score(self.nutricional)
        self.adaptativo = normalizar_score(self.adaptativo)

    def score_global(self) -> float:
        pesos = {
            "fisico": 0.25,
            "psicologico": 0.20,
            "fisiologico": 0.25,
            "nutricional": 0.10,
            "adaptativo": 0.20
        }

        score = (
            self.fisico * pesos["fisico"] +
            self.psicologico * pesos["psicologico"] +
            self.fisiologico * pesos["fisiologico"] +
            self.nutricional * pesos["nutricional"] +
            self.adaptativo * pesos["adaptativo"]
        )

        return round(score, 2)

    def possui_risco_critico(self) -> bool:
        dimensoes = [
            self.fisico,
            self.psicologico,
            self.fisiologico,
            self.nutricional,
            self.adaptativo
        ]

        return any(score < 20 for score in dimensoes)

    def classificar_estado(self) -> EstadoGlobal:

        if self.possui_risco_critico():
            return EstadoGlobal.EM_RISCO

        score = self.score_global()

        if score >= 85:
            return EstadoGlobal.PICO_FUNCIONAL
        elif score >= 70:
            return EstadoGlobal.ADAPTANDO
        elif score >= 55:
            return EstadoGlobal.ESTAVEL
        elif score >= 40:
            return EstadoGlobal.EM_ALERTA
        else:
            return EstadoGlobal.EM_RISCO

    def resumo(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "scores": {
                "fisico": self.fisico,
                "psicologico": self.psicologico,
                "fisiologico": self.fisiologico,
                "nutricional": self.nutricional,
                "adaptativo": self.adaptativo
            },
            "score_global": self.score_global(),
            "estado_global": self.classificar_estado().value,
            "risco_critico": self.possui_risco_critico()
        }
