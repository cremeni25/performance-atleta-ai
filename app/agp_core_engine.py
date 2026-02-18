# ==========================================
# MOTOR GLOBAL DE PERFORMANCE DO ATLETA v1
# Núcleo Científico + Adaptativo
# ==========================================

import numpy as np

# ==========================================
# CLASSE DO ATLETA
# ==========================================

class Athlete:

    def __init__(self, profile, data, history=None):
        self.profile = profile
        self.data = data
        self.history = history if history else []

        self.normalized_data = {}
        self.subdimensions = {}
        self.dimensions = {}
        self.scientific_score = 0
        self.adaptive_score = 0
        self.final_score = 0


# ==========================================
# NORMALIZAÇÃO
# ==========================================

class Normalizer:

    @staticmethod
    def normalize(value, min_val, max_val, inverse=False):
        score = ((value - min_val) / (max_val - min_val)) * 100
        return 100 - score if inverse else score


# ==========================================
# MOTOR CIENTÍFICO
# ==========================================

class ScientificEngine:

    BASE_WEIGHTS = {
        "fisiologica": 0.25,
        "tecnica": 0.20,
        "recuperacao": 0.20,
        "psicologica": 0.15,
        "fisica": 0.10,
        "contextual": 0.10
    }

    def calculate_subdimensions(self, athlete):
        athlete.subdimensions = athlete.normalized_data

    def calculate_dimensions(self, athlete):
        for dim, values in athlete.subdimensions.items():
            athlete.dimensions[dim] = np.mean(values)

    def calculate_scientific_score(self, athlete):
        total = 0
        for dim, score in athlete.dimensions.items():
            weight = self.BASE_WEIGHTS.get(dim, 0)
            total += score * weight

        athlete.scientific_score = total


# ==========================================
# MOTOR ADAPTATIVO
# ==========================================

class AdaptiveEngine:

    def adjust_weights(self, athlete):
        profile = athlete.profile
        weights = ScientificEngine.BASE_WEIGHTS.copy()

        # Ajuste por idade
        if profile["idade"] < 18:
            weights["fisiologica"] *= 1.1
            weights["psicologica"] *= 0.9

        # Ajuste por nível
        if profile["nivel"] == "elite":
            weights["tecnica"] *= 1.2
            weights["recuperacao"] *= 1.2

        # Normalizar pesos
        total = sum(weights.values())
        for k in weights:
            weights[k] /= total

        return weights

    def calculate_adaptive_score(self, athlete, weights):
        total = 0
        for dim, score in athlete.dimensions.items():
            total += score * weights.get(dim, 0)

        athlete.adaptive_score = total


# ==========================================
# MOTOR DE EVOLUÇÃO
# ==========================================

class EvolutionEngine:

    def calculate_trend(self, athlete):
        if len(athlete.history) < 2:
            return 0

        return athlete.history[-1] - athlete.history[-2]

    def calculate_consistency(self, athlete):
        if len(athlete.history) < 2:
            return 1

        return 1 - (np.std(athlete.history) / 100)


# ==========================================
# MOTOR DE RISCO
# ==========================================

class RiskEngine:

    def calculate_risk(self, athlete):
        trend = EvolutionEngine().calculate_trend(athlete)
        risk = 1 / (1 + np.exp(-trend))
        return risk * 100


# ==========================================
# MOTOR GLOBAL
# ==========================================

class GlobalPerformanceEngine:

    def __init__(self):
        self.scientific = ScientificEngine()
        self.adaptive = AdaptiveEngine()
        self.evolution = EvolutionEngine()
        self.risk = RiskEngine()

    def run(self, athlete):

        # 1. Calcular dimensões
        self.scientific.calculate_subdimensions(athlete)
        self.scientific.calculate_dimensions(athlete)

        # 2. Score científico
        self.scientific.calculate_scientific_score(athlete)

        # 3. Ajuste adaptativo
        weights = self.adaptive.adjust_weights(athlete)
        self.adaptive.calculate_adaptive_score(athlete, weights)

        # 4. Evolução
        trend = self.evolution.calculate_trend(athlete)
        consistency = self.evolution.calculate_consistency(athlete)

        # 5. Risco
        risk = self.risk.calculate_risk(athlete)

        # 6. Score final
        athlete.final_score = athlete.adaptive_score + trend + consistency - risk

        return athlete
