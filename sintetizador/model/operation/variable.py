from enum import Enum


class Variable(Enum):
    CUSTO_MARGINAL_OPERACAO = "CMO"
    VALOR_AGUA = "VAGUA"
    VALOR_AGUA_INCREMENTAL = "VAGUAI"
    CUSTO_GERACAO_TERMICA = "CTER"
    CUSTO_DEFICIT = "CDEF"
    CUSTO_OPERACAO = "COP"
    CUSTO_FUTURO = "CFU"
    ENERGIA_NATURAL_AFLUENTE_ABSOLUTA_RESERVATORIO = "ENAAR"
    ENERGIA_NATURAL_AFLUENTE_ABSOLUTA_FIO = "ENAAF"
    ENERGIA_NATURAL_AFLUENTE_ABSOLUTA = "ENAA"
    ENERGIA_ARMAZENADA_ABSOLUTA_INICIAL = "EARMI"
    ENERGIA_ARMAZENADA_PERCENTUAL_INICIAL = "EARPI"
    ENERGIA_ARMAZENADA_ABSOLUTA_FINAL = "EARMF"
    ENERGIA_ARMAZENADA_PERCENTUAL_FINAL = "EARPF"
    GERACAO_HIDRAULICA_RESERVATORIO = "GHIDR"
    GERACAO_HIDRAULICA_FIO = "GHIDF"
    GERACAO_HIDRAULICA = "GHID"
    COTA_MONTANTE = "HMON"
    COTA_JUSANTE = "HJUS"
    QUEDA_LIQUIDA = "HLIQ"
    GERACAO_TERMICA = "GTER"
    GERACAO_EOLICA = "GEOL"
    ENERGIA_VERTIDA = "EVER"
    ENERGIA_VERTIDA_TURBINAVEL = "EVERT"
    ENERGIA_VERTIDA_NAO_TURBINAVEL = "EVERNT"
    ENERGIA_VERTIDA_RESERV = "EVERR"
    ENERGIA_VERTIDA_RESERV_TURBINAVEL = "EVERRT"
    ENERGIA_VERTIDA_RESERV_NAO_TURBINAVEL = "EVERRNT"
    ENERGIA_VERTIDA_FIO = "EVERF"
    ENERGIA_VERTIDA_FIO_TURBINAVEL = "EVERFT"
    ENERGIA_VERTIDA_FIO_NAO_TURBINAVEL = "EVERFNT"
    ENERGIA_DESVIO_RESERVATORIO = "EDESR"
    ENERGIA_DESVIO_FIO = "EDESF"
    META_ENERGIA_DEFLUENCIA_MINIMA = "MEVMIN"
    ENERGIA_DEFLUENCIA_MINIMA = "EVMIN"
    ENERGIA_VOLUME_MORTO = "EVMOR"
    ENERGIA_EVAPORACAO = "EEVAP"
    VAZAO_AFLUENTE = "QAFL"
    VAZAO_DEFLUENTE = "QDEF"
    VAZAO_INCREMENTAL = "QINC"
    VAZAO_TURBINADA = "QTUR"
    VAZAO_VERTIDA = "QVER"
    VAZAO_RETIRADA = "QRET"
    VAZAO_DESVIADA = "QDES"
    VELOCIDADE_VENTO = "VENTO"
    VOLUME_ARMAZENADO_ABSOLUTO_INICIAL = "VARMI"
    VOLUME_ARMAZENADO_PERCENTUAL_INICIAL = "VARPI"
    VOLUME_ARMAZENADO_ABSOLUTO_FINAL = "VARMF"
    VOLUME_ARMAZENADO_PERCENTUAL_FINAL = "VARPF"
    VOLUME_AFLUENTE = "VAFL"
    VOLUME_INCREMENTAL = "VINC"
    VOLUME_DEFLUENTE = "VDEF"
    VOLUME_VERTIDO = "VVER"
    VOLUME_TURBINADO = "VTUR"
    VOLUME_RETIRADO = "VRET"
    VOLUME_DESVIADO = "VDES"
    INTERCAMBIO = "INT"
    MERCADO = "MER"
    MERCADO_LIQUIDO = "MERL"
    USINAS_NAO_SIMULADAS = "UNSI"
    DEFICIT = "DEF"
    EXCESSO = "EXC"
    VIOLACAO_GERACAO_HIDRAULICA_MINIMA = "VGHMIN"
    VIOLACAO_DEFLUENCIA_MINIMA = "VDEFMIN"
    VIOLACAO_DEFLUENCIA_MAXIMA = "VDEFMAX"
    VIOLACAO_TURBINAMENTO_MINIMO = "VTURMIN"
    VIOLACAO_TURBINAMENTO_MAXIMO = "VTURMAX"
    VIOLACAO_ENERGIA_DEFLUENCIA_MINIMA = "VEVMIN"
    VIOLACAO_VMINOP = "VVMINOP"
    VIOLACAO_FPHA = "VFPHA"
    CORTE_GERACAO_EOLICA = "VEOL"

    @classmethod
    def factory(cls, val: str) -> "Variable":
        for v in cls:
            if v.value == val:
                return v
        return cls.ENERGIA_ARMAZENADA_PERCENTUAL_FINAL

    def __repr__(self) -> str:
        return self.value
