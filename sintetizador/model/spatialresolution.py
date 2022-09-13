from enum import Enum


class SpatialResolution(Enum):
    SISTEMA_INTERLIGADO = "SIN"
    SUBMERCADO = "SBM"
    RESERVATORIO_EQUIVALENTE = "REE"
    USINA_HIDROELETRICA = "UHE"
    USINA_TERMELETRICA = "UTE"
    USINA_EOLICA = "UEE"
