import numpy as np


def analisar_tendencia(scores):

    if len(scores) < 3:
        return "Dados insuficientes"

    x = np.arange(len(scores))
    y = np.array(scores)

    coef = np.polyfit(x, y, 1)[0]

    if coef > 0.5:
        return "Evolução positiva"
    elif coef < -0.5:
        return "Queda de performance"
    else:
        return "Estabilidade"


def detectar_risco(scores):

    if len(scores) < 4:
        return None

    ultimos = scores[-4:]

    if all(x > y for x, y in zip(ultimos, ultimos[1:])):
        return "Risco de queda contínua"

    return None


def prever_nivel(score_atual):

    if score_atual < 60:
        return "Potencial para atingir nível competitivo em médio prazo"
    elif score_atual < 75:
        return "Próximo do alto rendimento"
    else:
        return "Perfil próximo da elite"
