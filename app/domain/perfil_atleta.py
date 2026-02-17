# =========================================================
# perfil_atleta.py
# Núcleo Contextual do Atleta (Perfil Fixo)
# =========================================================

from dataclasses import dataclass
from enum import Enum


class Sexo(Enum):
    MASCULINO = "MASCULINO"
    FEMININO = "FEMININO"


class NivelAtleta(Enum):
    SAUDE = "SAUDE"
    COMPETITIVO = "COMPETITIVO"
    ALTO_RENDIMENTO = "ALTO_RENDIMENTO"


class Esporte(Enum):
    NATACAO = "NATACAO"
    VOLEI = "VOLEI"
    FUTEBOL = "FUTEBOL"
    BASQUETE = "BASQUETE"
    ATLETISMO = "ATLETISMO"


class FaixaEtaria(Enum):
    INFANTO_JUVENIL = "INFANTO_JUVENIL"
    JUVENIL = "JUVENIL"
    ADULTO = "ADULTO"
    MASTER = "MASTER"


def classificar_faixa_etaria(idade: int) -> FaixaEtaria:
    if idade <= 14:
        return FaixaEtaria.INFANTO_JUVENIL
    elif idade <= 18:
        return FaixaEtaria.JUVENIL
    elif idade <= 35:
        return FaixaEtaria.ADULTO
    else:
        return FaixaEtaria.MASTER


LOCALIZACAO_SEMANTICA = {
    "ALTO_RENDIMENTO": {
        "pt": "Alto rendimento",
        "en": "Elite performance",
        "es": "Alto rendimiento",
        "fr": "Performance élite"
    },
    "COMPETITIVO": {
        "pt": "Competitivo",
        "en": "Competitive level",
        "es": "Nivel competitivo",
        "fr": "Niveau compétitif"
    },
    "SAUDE": {
        "pt": "Manutenção da saúde",
        "en": "Health maintenance",
        "es": "Mantenimiento de salud",
        "fr": "Maintien de la santé"
    }
}


def traduzir_semantico(chave: str, idioma: str = "pt") -> str:
    return LOCALIZACAO_SEMANTICA.get(chave, {}).get(idioma, chave)


@dataclass
class PerfilAtleta:
    nome: str
    idade: int
    sexo: Sexo
    esporte: Esporte
    nivel: NivelAtleta
    subtipo: str | None = None

    def faixa_etaria(self) -> FaixaEtaria:
        return classificar_faixa_etaria(self.idade)

    def resumo(self, idioma: str = "pt") -> dict:
        return {
            "nome": self.nome,
            "idade": self.idade,
            "sexo": self.sexo.value,
            "esporte": self.esporte.value,
            "subtipo": self.subtipo,
            "nivel": traduzir_semantico(self.nivel.value, idioma),
            "faixa_etaria": traduzir_semantico(self.faixa_etaria().value, idioma)
        }
