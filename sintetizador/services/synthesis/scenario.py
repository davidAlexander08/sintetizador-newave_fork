from typing import Callable, Dict, List, Tuple, Optional, TypeVar, Type
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import logging
from traceback import print_exc
from multiprocessing import Pool
from datetime import datetime
from dateutil.relativedelta import relativedelta  # type: ignore
from inewave.newave import Dger, Ree, Confhd, Conft, Hidr, Vazoes, Sistema, Pmo
from sintetizador.services.unitofwork import AbstractUnitOfWork
from sintetizador.utils.log import Log
from sintetizador.model.settings import Settings
from sintetizador.model.scenario.variable import Variable
from sintetizador.model.scenario.spatialresolution import SpatialResolution
from sintetizador.model.scenario.step import Step
from sintetizador.model.scenario.scenariosynthesis import ScenarioSynthesis


class ScenarioSynthetizer:
    DEFAULT_SCENARIO_SYNTHESIS_ARGS: List[str] = [
        "ENAA_REE_FOR",
        # "ENAA_REE_BKW",
        "ENAA_REE_SF",
        "ENAA_SBM_FOR",
        # "ENAA_SBM_BKW",
        "ENAA_SBM_SF",
        "ENAA_SIN_FOR",
        # "ENAA_SIN_BKW",
        "ENAA_SIN_SF",
        "QINC_UHE_FOR",
        # "QINC_UHE_BKW",
        "QINC_UHE_SF",
        "QINC_REE_FOR",
        # "QINC_REE_BKW",
        "QINC_REE_SF",
        "QINC_SBM_FOR",
        # "QINC_SBM_BKW",
        "QINC_SBM_SF",
        "QINC_SIN_FOR",
        # "QINC_SIN_BKW",
        "QINC_SIN_SF",
    ]

    COMMON_COLUMNS: List[str] = [
        "iteracao",
        "estagio",
        "data",
        "data_fim",
        "serie",
        "abertura",
    ]

    IDENTIFICATION_COLUMNS = [
        "dataInicio",
        "dataFim",
        "estagio",
        "submercado",
        "ree",
        "pee",
        "usina",
        "iteracao",
    ]

    CACHED_SYNTHESIS: Dict[Tuple[Variable, Step], pd.DataFrame] = {}

    CACHED_MLT_VALUES: Dict[
        Tuple[Variable, SpatialResolution], pd.DataFrame
    ] = {}

    T = TypeVar("T")

    logger: Optional[logging.Logger] = None

    @classmethod
    def _default_args(cls) -> List[ScenarioSynthesis]:
        args = [
            ScenarioSynthesis.factory(a)
            for a in cls.DEFAULT_SCENARIO_SYNTHESIS_ARGS
        ]
        return [arg for arg in args if arg is not None]

    @classmethod
    def _process_variable_arguments(
        cls,
        args: List[str],
    ) -> List[ScenarioSynthesis]:
        args_data = [ScenarioSynthesis.factory(c) for c in args]
        valid_args = [arg for arg in args_data if arg is not None]
        return valid_args

    @classmethod
    def _validate_data(cls, data, type: Type[T], msg: str = "dados") -> T:
        if not isinstance(data, type):
            if cls.logger is not None:
                cls.logger.error(f"Erro na leitura de {msg}")
            raise RuntimeError()
        return data

    @classmethod
    def _validate_spatial_resolution_request(
        cls, spatial_resolution: SpatialResolution, *args, **kwargs
    ) -> bool:
        RESOLUTION_ARGS_MAP: Dict[SpatialResolution, List[str]] = {
            SpatialResolution.SISTEMA_INTERLIGADO: [],
            SpatialResolution.SUBMERCADO: ["submercado"],
            SpatialResolution.RESERVATORIO_EQUIVALENTE: ["ree"],
            SpatialResolution.USINA_HIDROELETRICA: ["uhe"],
        }

        mandatory = RESOLUTION_ARGS_MAP[spatial_resolution]
        valid = all([a in kwargs.keys() for a in mandatory])
        if not valid:
            if cls.logger is not None:
                cls.logger.error(
                    f"Erro no processamento da informação por {spatial_resolution}"
                )
        return valid

    @classmethod
    def _get_dger(cls, uow: AbstractUnitOfWork) -> Dger:
        with uow:
            dger = uow.files.get_dger()
            if dger is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do dger.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return dger

    @classmethod
    def _get_ree(cls, uow: AbstractUnitOfWork) -> Ree:
        with uow:
            ree = uow.files.get_ree()
            if ree is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do ree.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return ree

    @classmethod
    def _get_confhd(cls, uow: AbstractUnitOfWork) -> Confhd:
        with uow:
            confhd = uow.files.get_confhd()
            if confhd is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do confhd.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return confhd

    @classmethod
    def _get_conft(cls, uow: AbstractUnitOfWork) -> Conft:
        with uow:
            conft = uow.files.get_conft()
            if conft is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do conft.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return conft

    @classmethod
    def _get_hidr(cls, uow: AbstractUnitOfWork) -> Hidr:
        with uow:
            hidr = uow.files.get_hidr()
            if hidr is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do hidr.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return hidr

    @classmethod
    def _get_sistema(cls, uow: AbstractUnitOfWork) -> Sistema:
        with uow:
            sist = uow.files.get_sistema()
            if sist is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do sistema.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return sist

    @classmethod
    def _get_vazoes(cls, uow: AbstractUnitOfWork) -> Vazoes:
        with uow:
            vaz = uow.files.get_vazoes()
            if vaz is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do vazoes.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return vaz

    @classmethod
    def _get_pmo(cls, uow: AbstractUnitOfWork) -> Pmo:
        with uow:
            vaz = uow.files.get_pmo()
            if vaz is None:
                if cls.logger is not None:
                    cls.logger.error(
                        "Erro no processamento do pmo.dat para"
                        + " síntese dos cenários"
                    )
                raise RuntimeError()
            return vaz

    @classmethod
    def filter_valid_variables(
        cls, variables: List[ScenarioSynthesis], uow: AbstractUnitOfWork
    ) -> List[ScenarioSynthesis]:
        dger = cls._get_dger(uow)
        ree = cls._get_ree(uow)
        valid_variables: List[ScenarioSynthesis] = []
        sf_indiv = dger.agregacao_simulacao_final == 1
        rees = cls._validate_data(ree.rees, pd.DataFrame, "REEs")
        politica_indiv = rees["mes_fim_individualizado"].isna().sum() == 0
        indiv = sf_indiv or politica_indiv
        eolica = dger.considera_geracao_eolica != 0
        if cls.logger is not None:
            cls.logger.info(
                f"Caso com geração de cenários de eólica: {eolica}"
            )
            cls.logger.info(f"Caso com modelagem híbrida: {indiv}")
        for v in variables:
            if v.variable == Variable.VAZAO_INCREMENTAL and not indiv:
                continue
            valid_variables.append(v)
        if cls.logger is not None:
            cls.logger.info(f"Variáveis: {valid_variables}")
        return valid_variables

    @classmethod
    def _gera_serie_incremental_uhe(
        cls, uhe: int, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        """
        Obtém a série histórica de vazões incrementais para uma UHE.

        - data (`datetime`)
        - vazao (`float`)

        :return: A tabela como um DataFrame
        :rtype: pd.DataFrame | None
        """
        arq_confhd = uow.files.get_confhd()
        if arq_confhd is None:
            if cls.logger is not None:
                cls.logger.error(
                    "Erro no processamento do confhd.dat para"
                    + " síntese dos cenários"
                )
            raise RuntimeError()
        uhes = cls._validate_data(arq_confhd.usinas, pd.DataFrame, "UHEs")
        arq_hidr = uow.files.get_hidr()
        if arq_hidr is None:
            if cls.logger is not None:
                cls.logger.error(
                    "Erro no processamento do hidr.dat para"
                    + " síntese dos cenários"
                )
            raise RuntimeError()
        hidr = cls._validate_data(arq_hidr.cadastro, pd.DataFrame, "hidr")
        arq_vazoes = uow.files.get_vazoes()
        if arq_vazoes is None:
            if cls.logger is not None:
                cls.logger.error(
                    "Erro no processamento do vazoes.dat para"
                    + " síntese dos cenários"
                )
            raise RuntimeError()
        vazoes = cls._validate_data(arq_vazoes.vazoes, pd.DataFrame, "vazões")
        posto = uhes.loc[uhes["codigo_usina"] == uhe, "posto"].tolist()[0]
        vazao_natural = vazoes[posto].to_numpy()
        posto_nulo = posto == 300
        if not posto_nulo:
            uhes_montante = uhes.loc[
                uhes["codigo_usina_jusante"] == uhe, "codigo_usina"
            ].tolist()
            uhes_montante = [u for u in uhes_montante if u != 0]
            postos_montante = list(
                set(
                    [
                        hidr.at[int(uhe_montante), "posto"]
                        for uhe_montante in uhes_montante
                    ]
                )
            )
            for posto_montante in postos_montante:
                vazao_natural = (
                    vazao_natural - vazoes[posto_montante].to_numpy()
                )
        ano_inicio_historico = int(
            uhes.loc[uhes["codigo_usina"] == uhe, "ano_inicio_historico"].iloc[
                0
            ]
        )
        ano_fim_historico = int(
            uhes.loc[uhes["codigo_usina"] == uhe, "ano_fim_historico"].iloc[0]
        )
        datas = pd.date_range(
            datetime(year=ano_inicio_historico, month=1, day=1),
            datetime(year=ano_fim_historico, month=12, day=1),
            freq="MS",
        )
        return pd.DataFrame(
            data={
                "data": datas,
                "vazao": vazao_natural[: len(datas)],
            }
        )

    @classmethod
    def _mlt(cls, serie_historica: pd.DataFrame) -> pd.DataFrame:
        """
        Extrai a MLT de uma série histórica de vazões de
        uma UHE, agrupando por mês.

        - mes (`int`)
        - vazao (`float`)

        :return: A tabela como um DataFrame
        :rtype: pd.DataFrame | None
        """
        serie_historica["mes"] = serie_historica.apply(
            lambda linha: linha["data"].month, axis=1
        )
        return (
            serie_historica.groupby(["mes"])
            .mean(numeric_only=True)
            .reset_index()
        )

    @classmethod
    def _gera_series_vazao_mlt_uhes(
        cls, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        """
        Extrai a MLT para todas as UHEs.

        - codigo_usina (`int`)
        - nome_usina (`str`)
        - codigo_ree (`int`)
        - nome_ree (`str`)
        - codigo_submercado (`int`)
        - nome_submercado (`str`)
        - estagio (`int`)
        - mes (`int`)
        - mlt (`float`)

        :return: A tabela como um DataFrame
        :rtype: pd.DataFrame | None
        """
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para QINC - UHE")
        uhes = cls._validate_data(
            cls._get_confhd(uow).usinas, pd.DataFrame, "UHEs"
        )
        rees = cls._validate_data(cls._get_ree(uow).rees, pd.DataFrame, "REEs")
        hidr = cls._validate_data(
            cls._get_hidr(uow).cadastro, pd.DataFrame, "hidr"
        )
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "vazões"
        )
        dger = cls._get_dger(uow)
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")
        anos_estudo = cls._validate_data(dger.num_anos_estudo, int, "dger")
        datas = pd.date_range(
            datetime(year=ano_inicio - 1, month=1, day=1),
            datetime(year=ano_inicio + anos_estudo - 1, month=12, day=1),
            freq="MS",
        )
        df_mlt = pd.DataFrame(
            data={
                "estagio": list(
                    range(
                        -(12 + mes_inicio - 2),
                        12 * anos_estudo - mes_inicio + 2,
                    )
                ),
                "mes": [d.month for d in datas],
            }
        )
        df_completo_mlt = pd.DataFrame()
        # Modificação por desempenho:
        # Abre o contexto do UoW antes de iterar para não repetir leituras
        # de arquivos de maneira desnecessária
        with uow:
            for uhe in uhes["codigo_usina"]:
                vazao = cls._gera_serie_incremental_uhe(uhe, uow)
                vazao_mlt = cls._mlt(vazao)
                df_mlt_uhe = df_mlt.merge(
                    pd.DataFrame(
                        data={
                            "codigo_usina": [uhe] * len(vazao_mlt),
                            "nome_usina": [hidr.at[uhe, "nome_usina"]]
                            * len(vazao_mlt),
                            "mes": vazao_mlt["mes"],
                            "mlt": vazao_mlt["vazao"].to_numpy(),
                        }
                    ),
                    on="mes",
                )
                df_completo_mlt = pd.concat(
                    [df_completo_mlt, df_mlt_uhe], ignore_index=True
                )
        # Adiciona dados de ree e submercado à série
        df_completo_mlt["codigo_ree"] = df_completo_mlt.apply(
            lambda linha: uhes.loc[
                uhes["codigo_usina"] == linha["codigo_usina"], "ree"
            ].tolist()[0],
            axis=1,
        )
        df_completo_mlt["nome_ree"] = df_completo_mlt.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha["codigo_ree"], "nome"
            ].tolist()[0],
            axis=1,
        )
        df_completo_mlt["codigo_submercado"] = df_completo_mlt.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha["codigo_ree"], "submercado"
            ].tolist()[0],
            axis=1,
        )
        df_completo_mlt["nome_submercado"] = df_completo_mlt.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha["codigo_submercado"],
                "nome_submercado",
            ].tolist()[0],
            axis=1,
        )
        return df_completo_mlt.sort_values(["estagio", "codigo_usina"])

    @classmethod
    def _gera_series_energia_mlt_rees(
        cls, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        """
        Extrai a MLT para todos os REEs.

        - codigo_ree (`int`)
        - nome_ree (`str`)
        - codigo_submercado (`int`)
        - nome_submercado (`str`)
        - estagio (`int`)
        - configuracao (`int`)
        - mes (`int`)
        - mlt (`float`)

        :return: A tabela como um DataFrame
        :rtype: pd.DataFrame | None
        """
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para ENAA - REE")
        # Monta um df com estagio | configuracao | mes
        configuracoes = cls._validate_data(
            cls._get_pmo(uow).configuracoes_qualquer_modificacao,
            pd.DataFrame,
            "configurações",
        )
        dger = cls._get_dger(uow)
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")
        anos_estudo = cls._validate_data(dger.num_anos_estudo, int, "dger")
        #anos_pos_estudo = cls._validate_data(dger.num_anos_pos_estudo, int, "dger")
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        rees = cls._validate_data(cls._get_ree(uow).rees, pd.DataFrame, "REEs")
        with uow:
            arq_engnat = uow.files.get_engnat()
            if arq_engnat is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de energia")
                raise RuntimeError()
        engnat = cls._validate_data(
            arq_engnat.series, pd.DataFrame, "séries de energia"
        )
        cfgs = configuracoes["valor"].to_numpy().flatten()[mes_inicio - 1 :]
        cfgs = list( dict.fromkeys(cfgs) )
        print("cfgs: ", cfgs)
        print("configuracoes[valor].to_numpy().flatten(): ", configuracoes["valor"].to_numpy().flatten())
        datas = pd.date_range(
            datetime(year=ano_inicio - 1, month=1, day=1),
            #datetime(year=ano_inicio + anos_estudo + anos_pos_estudo - 1, month=12, day=1),
            datetime(year=ano_inicio + anos_estudo - 1, month=12, day=1),
            freq="MS",
        )
        print("list(range(-(12 + mes_inicio - 2), len(cfgs) + 1)): ", list(range(-(12 + mes_inicio - 2), len(cfgs) + 1)))
        print("np.concatenate((np.array([1] * (12 + mes_inicio - 1)), cfgs)): ", np.concatenate((np.array([1] * (12 + mes_inicio - 1)), cfgs)))
        print("[d.month for d in datas] } : ", [d.month for d in datas] )

        
        df_mlt = pd.DataFrame(data={"estagio": list(range(-(12 + mes_inicio - 2), len(cfgs) + 1)),
                                    "configuracao": np.concatenate((np.array([1] * (12 + mes_inicio - 1)), cfgs)),
                                   "mes": [d.month for d in datas] } )
        
        dfs_mlt_rees = pd.DataFrame()
        # Para cada REE, obtem a série de MLT para os estágios do modelo
        ano_limite_historico = ano_inicio - 1
        engnat = engnat.loc[engnat["data"].dt.year <= ano_limite_historico]
        for idx, linha in rees.iterrows():
            ree_engnat = idx + 1
            mlt_ree = np.zeros((df_mlt.shape[0],))
            for idx_ree, linha_mlt in df_mlt.iterrows():
                mlt = engnat.loc[
                    (engnat["configuracao"] == linha_mlt["configuracao"])
                    & (engnat["ree"] == ree_engnat)
                    & (engnat["data"].dt.month == linha_mlt["mes"]),
                    "valor",
                ].mean()
                mlt_ree[idx_ree] = mlt
            df_mlt_ree = df_mlt.copy()
            df_mlt_ree["mlt"] = mlt_ree
            df_mlt_ree["codigo_ree"] = linha["codigo"]
            df_mlt_ree["nome_ree"] = linha["nome"]
            df_mlt_ree["codigo_submercado"] = linha["submercado"]
            df_mlt_ree["nome_submercado"] = sistema.loc[
                sistema["codigo_submercado"] == linha["submercado"],
                "nome_submercado",
            ].iloc[0]
            dfs_mlt_rees = pd.concat(
                [dfs_mlt_rees, df_mlt_ree], ignore_index=True
            )
        return dfs_mlt_rees

    @classmethod
    def _engolimento_maximo_uhes(
        cls, uow: AbstractUnitOfWork
    ) -> Dict[int, float]:
        hidr = cls._get_hidr(uow).cadastro
        engolimentos: Dict[int, float] = {}
        for idx, linha in hidr.iterrows():
            engol_max = 0.0
            n_conj = linha["numero_conjuntos_maquinas"]
            for i in range(1, n_conj + 1):
                n_maq = linha[f"numero_maquinas_conjunto_{i}"]
                qef_maq = linha[f"vazao_nominal_conjunto_{i}"]
                engol_max += n_maq * qef_maq
            engolimentos[idx] = engol_max
        return engolimentos

    @classmethod
    def _agrega_serie_mlt_uhe(
        cls, variavel: Variable, col: Optional[str], uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        mlt_uhe = cls._get_cached_mlt(
            variavel,
            SpatialResolution.USINA_HIDROELETRICA,
            uow,
        )
        col_list = [col] if col is not None else []

        print("col_list: ", col_list)
        print("mlt_uhe: ", mlt_uhe)
        df = (
            mlt_uhe.groupby(col_list + ["estagio"])
            .sum(numeric_only=True)
            .reset_index()
        )
        return df[col_list + ["estagio", "mlt"]]

    @classmethod
    def _agrega_serie_mlt_enaa(
        cls, col: Optional[str], uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        mlt_ree = cls._get_cached_mlt(
            Variable.ENA_ABSOLUTA,
            SpatialResolution.RESERVATORIO_EQUIVALENTE,
            uow,
        )
        col_list = [col] if col is not None else []
        df = (
            mlt_ree.groupby(col_list + ["estagio"])
            .sum(numeric_only=True)
            .reset_index()
        )
        return df[col_list + ["estagio", "mlt"]]

    @classmethod
    def _resolve_enaa_mlt_submercado(
        cls, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para ENAA - SBM")
        return cls._agrega_serie_mlt_enaa("nome_submercado", uow)

    @classmethod
    def _resolve_enaa_mlt_sin(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para ENAA - SIN")
        return cls._agrega_serie_mlt_enaa(None, uow)

    @classmethod
    def _resolve_qinc_mlt_ree(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para QINC - REE")
        return cls._agrega_serie_mlt_uhe(
            #Variable.VAZAO_INCREMENTAL, "nome_usina", uow
            Variable.VAZAO_INCREMENTAL, "nome_ree", uow
        )

    @classmethod
    def _resolve_qinc_mlt_submercado(
        cls, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para QINC - SBM")
        return cls._agrega_serie_mlt_uhe(
            Variable.VAZAO_INCREMENTAL, "nome_submercado", uow
        )

    @classmethod
    def _resolve_qinc_mlt_sin(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        if cls.logger is not None:
            cls.logger.info("Calculando séries de MLT para QINC - SIN")
        return cls._agrega_serie_mlt_uhe(Variable.VAZAO_INCREMENTAL, None, uow)

    @classmethod
    def _get_cached_mlt(
        cls,
        variable: Variable,
        spatial_resolution: SpatialResolution,
        uow: AbstractUnitOfWork,
    ) -> pd.DataFrame:
        CACHING_FUNCTION_MAP: Dict[
            Tuple[Variable, SpatialResolution], Callable
        ] = {
            (
                Variable.ENA_ABSOLUTA,
                SpatialResolution.RESERVATORIO_EQUIVALENTE,
            ): cls._gera_series_energia_mlt_rees,
            (
                Variable.ENA_ABSOLUTA,
                SpatialResolution.SUBMERCADO,
            ): cls._resolve_enaa_mlt_submercado,
            (
                Variable.ENA_ABSOLUTA,
                SpatialResolution.SISTEMA_INTERLIGADO,
            ): cls._resolve_enaa_mlt_sin,
            (
                Variable.VAZAO_INCREMENTAL,
                SpatialResolution.USINA_HIDROELETRICA,
            ): cls._gera_series_vazao_mlt_uhes,
            (
                Variable.VAZAO_INCREMENTAL,
                SpatialResolution.RESERVATORIO_EQUIVALENTE,
            ): cls._resolve_qinc_mlt_ree,
            (
                Variable.VAZAO_INCREMENTAL,
                SpatialResolution.SUBMERCADO,
            ): cls._resolve_qinc_mlt_submercado,
            (
                Variable.VAZAO_INCREMENTAL,
                SpatialResolution.SISTEMA_INTERLIGADO,
            ): cls._resolve_qinc_mlt_sin,
        }
        if cls.CACHED_MLT_VALUES.get((variable, spatial_resolution)) is None:
            cls.CACHED_MLT_VALUES[
                (variable, spatial_resolution)
            ] = CACHING_FUNCTION_MAP[(variable, spatial_resolution)](uow)
        return cls.CACHED_MLT_VALUES.get(
            (variable, spatial_resolution), pd.DataFrame()
        )

    @classmethod
    def _formata_dados_series(
        cls, dados: np.ndarray, n_series: int, n_estagios: int
    ) -> np.ndarray:
        return np.tile(np.repeat(dados, n_series), (n_estagios,))

    @classmethod
    def _adiciona_dados_rees_forward(
        cls, uow: AbstractUnitOfWork, energiaf: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados do REE aos dados de energia lidos do arquivo
        binário `energiaf.dat`.

        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - codigo_ree (`int`)
        - nome_ree (`str`)
        - codigo_submercado (`int`)
        - nome_submercado (`str`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        energiaf_dados = energiaf.copy()
        series = energiaf_dados["serie"].unique()
        num_series = len(series)
        rees = energiaf_dados["ree"].unique()
        num_rees = len(rees)
        estagios = energiaf_dados["estagio"].unique()
        num_estagios = len(estagios)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        anos_estudo = cls._validate_data(dger.num_anos_estudo, int, "dger")
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        dados_rees = cls._validate_data(
            cls._get_ree(uow).rees, pd.DataFrame, "REEs"
        )
        dados_rees["nome_submercado"] = dados_rees.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha["submercado"],
                "nome_submercado",
            ].tolist()[0],
            axis=1,
        )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaof
        codigos_ordenados = cls._formata_dados_series(
            dados_rees["codigo"].to_numpy(), num_series, num_estagios
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_rees["nome"].to_numpy(), num_series, num_estagios
        )
        submercados_ordenados = cls._formata_dados_series(
            dados_rees["submercado"].to_numpy(),
            num_series,
            num_estagios,
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_rees["nome_submercado"].to_numpy(), num_series, num_estagios
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio + anos_estudo - 1,
                month=12,
                day=1,
            ),
            freq="MS",
        )
        datas_ordenadas = np.repeat(datas, num_series * num_rees)
        # Edita o DF e retorna
        energiaf_dados["codigo_ree"] = codigos_ordenados
        energiaf_dados["nome_ree"] = nomes_ordenados
        energiaf_dados["codigo_submercado"] = submercados_ordenados
        energiaf_dados["nome_submercado"] = nomes_submercados_ordenados
        energiaf_dados["data"] = datas_ordenadas
        energiaf_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        energiaf_dados["estagio"] -= mes_inicio - 1
        energiaf_dados = energiaf_dados.loc[energiaf_dados["estagio"] > 0]
        return energiaf_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _adiciona_dados_uhes_forward(
        cls, uow: AbstractUnitOfWork, vazaof: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados de código da UHE, nome da UHE, ree da UHE e
        submercado da UHE aos dados de vazão lidos do arquivo
        binário `vazaof.dat`.

        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - codigo_usina (`int`)
        - nome_usina (`str`)
        - codigo_ree (`int`)
        - nome_ree (`str`)
        - codigo_submercado (`int`)
        - nome_submercado (`str`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        # Extrai dimensões para repetir vetores
        vazaof_dados = vazaof.copy()
        series = vazaof_dados["serie"].unique()
        num_series = len(series)
        uhes = vazaof_dados["uhe"].unique()
        num_uhes = len(uhes)
        estagios = vazaof_dados["estagio"].unique()
        num_estagios = len(estagios)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        confhd = cls._validate_data(
            cls._get_confhd(uow).usinas, pd.DataFrame, "UHEs"
        )
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        rees = cls._validate_data(cls._get_ree(uow).rees, pd.DataFrame, "REEs")
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")

        dados_uhes = pd.DataFrame(uhes).apply(
            lambda linha: confhd.loc[
                linha[0] - 1, ["codigo_usina", "nome_usina", "ree"]
            ].tolist(),
            axis=1,
            result_type="expand",
        )
        dados_uhes[3] = dados_uhes.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha[2], "nome"
            ].tolist()[0],
            axis=1,
        )
        dados_uhes[4] = dados_uhes.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha[2], "submercado"
            ].tolist()[0],
            axis=1,
        )
        dados_uhes[5] = dados_uhes.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha[4], "nome_submercado"
            ].tolist()[0],
            axis=1,
        )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaof
        codigos_ordenados = cls._formata_dados_series(
            dados_uhes[0].to_numpy(), num_series, num_estagios
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_uhes[1].to_numpy(), num_series, num_estagios
        )
        codigos_rees_ordenados = cls._formata_dados_series(
            dados_uhes[2].to_numpy(), num_series, num_estagios
        )
        nomes_rees_ordenados = cls._formata_dados_series(
            dados_uhes[3].to_numpy(), num_series, num_estagios
        )
        codigos_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[4].to_numpy(), num_series, num_estagios
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[5].to_numpy(), num_series, num_estagios
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            )
            + relativedelta(months=num_estagios - 1),
            freq="MS",
        )
        datas_ordenadas = np.repeat(datas, num_series * num_uhes)
        # Edita o DF e retorna
        vazaof_dados["codigo_usina"] = codigos_ordenados
        vazaof_dados["nome_usina"] = nomes_ordenados
        vazaof_dados["codigo_ree"] = codigos_rees_ordenados
        vazaof_dados["nome_ree"] = nomes_rees_ordenados
        vazaof_dados["codigo_submercado"] = codigos_submercados_ordenados
        vazaof_dados["nome_submercado"] = nomes_submercados_ordenados
        vazaof_dados["data"] = datas_ordenadas
        vazaof_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        
        vazaof_dados["estagio"] -= mes_inicio - 1
        vazaof_dados = vazaof_dados.loc[vazaof_dados["estagio"] > 0]
        vazaof_dados.drop(columns=["uhe"], inplace=True)

        return vazaof_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "codigo_usina",
                "nome_usina",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _adiciona_dados_rees_backward(
        cls, uow: AbstractUnitOfWork, energiab: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados de do REE aos dados de energia
        lidos do arquivo binário `energiab.dat`.

        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - abertura (`int`)
        - codigo_usina (`int`)
        - nome_usina (`str`)
        - ree (`int`)
        - submercado (`int`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        # Extrai dimensões para repetir vetores
        energiab_dados = energiab.copy()
        series = energiab_dados["serie"].unique()
        num_series = len(series)
        rees = energiab_dados["ree"].unique()
        num_rees = len(rees)
        estagios = energiab_dados["estagio"].unique()
        num_estagios = len(estagios)
        aberturas = energiab_dados["abertura"].unique()
        num_aberturas = len(aberturas)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        dados_rees = cls._validate_data(
            cls._get_ree(uow).rees, pd.DataFrame, "REEs"
        )
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")
        anos_estudo = cls._validate_data(dger.num_anos_estudo, int, "dger")

        dados_rees["nome_submercado"] = dados_rees.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha["submercado"],
                "nome_submercado",
            ].tolist()[0],
            axis=1,
        )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaob
        codigos_ordenados = cls._formata_dados_series(
            dados_rees["codigo"].to_numpy(),
            num_series * num_aberturas,
            num_estagios,
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_rees["nome"].to_numpy(),
            num_series * num_aberturas,
            num_estagios,
        )
        codigos_submercados_ordenados = cls._formata_dados_series(
            dados_rees["submercado"].to_numpy(),
            num_series * num_aberturas,
            num_estagios,
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_rees["nome_submercado"].to_numpy(),
            num_series * num_aberturas,
            num_estagios,
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio + anos_estudo - 1,
                month=12,
                day=1,
            ),
            freq="MS",
        )
        datas_ordenadas = np.repeat(
            datas, num_series * num_aberturas * num_rees
        )
        # Edita o DF e retorna
        energiab_dados["codigo_ree"] = codigos_ordenados
        energiab_dados["nome_ree"] = nomes_ordenados
        energiab_dados["codigo_submercado"] = codigos_submercados_ordenados
        energiab_dados["nome_submercado"] = nomes_submercados_ordenados
        energiab_dados["data"] = datas_ordenadas
        energiab_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        energiab_dados["estagio"] -= mes_inicio - 1
        energiab_dados = energiab_dados.loc[energiab_dados["estagio"] > 0]
        return energiab_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "abertura",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _adiciona_dados_uhes_backward(
        cls, uow: AbstractUnitOfWork, vazaob: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados de código da UHE, nome da UHE, ree da UHE e
        submercado da UHE aos dados de vazão lidos do arquivo
        binário `vazaob.dat`.

        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - abertura (`int`)
        - codigo_usina (`int`)
        - nome_usina (`str`)
        - codigo_ree (`int`)
        - nome_ree (`str`)
        - codigo_submercado (`int`)
        - nome_submercado (`str`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        # Extrai dimensões para repetir vetores
        vazaob_dados = vazaob.copy()
        series = vazaob_dados["serie"].unique()
        num_series = len(series)
        uhes = vazaob_dados["uhe"].unique()
        num_uhes = len(uhes)
        estagios = vazaob_dados["estagio"].unique()
        num_estagios = len(estagios)
        aberturas = vazaob_dados["abertura"].unique()
        num_aberturas = len(aberturas)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        confhd = cls._validate_data(
            cls._get_confhd(uow).usinas, pd.DataFrame, "UHEs"
        )
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        rees = cls._validate_data(cls._get_ree(uow).rees, pd.DataFrame, "REEs")
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")

        dados_uhes = pd.DataFrame(uhes).apply(
            lambda linha: confhd.loc[
                linha[0] - 1, ["codigo_usina", "nome_usina", "ree"]
            ].tolist(),
            axis=1,
            result_type="expand",
        )
        dados_uhes[3] = dados_uhes.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha[2], "nome"
            ].tolist()[0],
            axis=1,
        )
        dados_uhes[4] = dados_uhes.apply(
            lambda linha: rees.loc[
                rees["codigo"] == linha[2], "submercado"
            ].tolist()[0],
            axis=1,
        )
        dados_uhes[5] = dados_uhes.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha[4], "nome_submercado"
            ].tolist()[0],
            axis=1,
        )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaob
        codigos_ordenados = cls._formata_dados_series(
            dados_uhes[0].to_numpy(), num_series * num_aberturas, num_estagios
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_uhes[1].to_numpy(), num_series * num_aberturas, num_estagios
        )
        codigos_rees_ordenados = cls._formata_dados_series(
            dados_uhes[2].to_numpy(), num_series * num_aberturas, num_estagios
        )
        nomes_rees_ordenados = cls._formata_dados_series(
            dados_uhes[3].to_numpy(), num_series * num_aberturas, num_estagios
        )
        codigos_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[4].to_numpy(), num_series * num_aberturas, num_estagios
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[5].to_numpy(), num_series * num_aberturas, num_estagios
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            )
            + relativedelta(months=num_estagios - 1),
            freq="MS",
        )
        datas_ordenadas = np.repeat(
            datas, num_series * num_aberturas * num_uhes
        )
        # Edita o DF e retorna
        vazaob_dados["codigo_usina"] = codigos_ordenados
        vazaob_dados["nome_usina"] = nomes_ordenados
        vazaob_dados["codigo_ree"] = codigos_rees_ordenados
        vazaob_dados["nome_ree"] = nomes_rees_ordenados
        vazaob_dados["codigo_submercado"] = codigos_submercados_ordenados
        vazaob_dados["nome_submercado"] = nomes_submercados_ordenados
        vazaob_dados["data"] = datas_ordenadas
        vazaob_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        vazaob_dados["estagio"] -= mes_inicio - 1
        vazaob_dados = vazaob_dados.loc[vazaob_dados["estagio"] > 0]
        vazaob_dados.drop(columns=["uhe"], inplace=True)
        return vazaob_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "abertura",
                "codigo_usina",
                "nome_usina",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _adiciona_dados_rees_sf(
        cls, uow: AbstractUnitOfWork, energias: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados do REE aos dados de energia lidos do arquivo
        binário `energias.dat`.

        - codigo_ree (`int`)
        - ree (`str`)
        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        energias_dados = energias.copy()
        series = energias_dados["serie"].unique()
        num_series = len(series)
        rees = energias_dados["ree"].unique()
        num_rees = len(rees)
        estagios = energias_dados["estagio"].unique()
        num_estagios = len(estagios)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        dados_rees = cls._validate_data(
            cls._get_ree(uow).rees, pd.DataFrame, "REEs"
        )
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")
        anos_estudo = cls._validate_data(dger.num_anos_estudo, int, "dger")

        dados_rees["nome_submercado"] = dados_rees.apply(
            lambda linha: sistema.loc[
                sistema["codigo_submercado"] == linha["submercado"],
                "nome_submercado",
            ].tolist()[0],
            axis=1,
        )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaof
        codigos_ordenados = cls._formata_dados_series(
            dados_rees["codigo"].to_numpy(), num_series, num_estagios
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_rees["nome"].to_numpy(), num_series, num_estagios
        )
        submercados_ordenados = cls._formata_dados_series(
            dados_rees["submercado"].to_numpy(),
            num_series,
            num_estagios,
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_rees["nome_submercado"].to_numpy(), num_series, num_estagios
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio + anos_estudo - 1,
                month=12,
                day=1,
            ),
            freq="MS",
        )
        datas_ordenadas = np.repeat(datas, num_series * num_rees)
        # Edita o DF e retorna
        energias_dados["codigo_ree"] = codigos_ordenados
        energias_dados["nome_ree"] = nomes_ordenados
        energias_dados["codigo_submercado"] = submercados_ordenados
        energias_dados["nome_submercado"] = nomes_submercados_ordenados
        energias_dados["data"] = datas_ordenadas
        energias_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        energias_dados["estagio"] -= mes_inicio - 1
        energias_dados = energias_dados.loc[energias_dados["estagio"] > 0]
        return energias_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _adiciona_dados_uhes_sf(
        cls, uow: AbstractUnitOfWork, vazaos: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adiciona dados de código da UHE, nome da UHE, ree da UHE e
        submercado da UHE aos dados de vazão lidos do arquivo
        binário `vazaos.dat`.

        - estagio (`int`)
        - data (`datetime`)
        - data_fim (`datetime`)
        - serie (`int`)
        - codigo_uhe (`float`)
        - nome_uhe (`float`)
        - ree (`float`)
        - submercado (`float`)
        - valor (`float`)

        :return: Os dados como um DataFrame.
        :rtype: pd.DataFrame
        """
        # Extrai dimensões para repetir vetores

        
        vazaos_dados = vazaos.copy()
        print("vazaos_dados: ", vazaos_dados)
        series = vazaos_dados["serie"].unique()
        num_series = len(series)
        uhes = vazaos_dados["uhe"].unique()
        num_uhes = len(uhes)
        estagios = vazaos_dados["estagio"].unique()
        num_estagios = len(estagios)
        # Obtem os dados de cada usina
        dger = cls._get_dger(uow)
        confhd = cls._validate_data(
            cls._get_confhd(uow).usinas, pd.DataFrame, "UHEs"
        )
        sistema = cls._validate_data(
            cls._get_sistema(uow).custo_deficit, pd.DataFrame, "submercados"
        )
        rees = cls._validate_data(cls._get_ree(uow).rees, pd.DataFrame, "REEs")
        mes_inicio = cls._validate_data(dger.mes_inicio_estudo, int, "dger")
        ano_inicio = cls._validate_data(dger.ano_inicio_estudo, int, "dger")

        dados_uhes = pd.DataFrame(uhes).apply(   lambda linha: confhd.loc[ linha[0] - 1, ["codigo_usina", "nome_usina", "ree"] ].tolist(),  axis=1,   result_type="expand"  )
        dados_uhes[3] = dados_uhes.apply(   lambda linha: rees.loc[    rees["codigo"] == linha[2], "nome"   ].tolist()[0],   axis=1,  )
        dados_uhes[4] = dados_uhes.apply(     lambda linha: rees.loc[    rees["codigo"] == linha[2], "submercado"     ].tolist()[0],  axis=1,   )
        dados_uhes[5] = dados_uhes.apply(    lambda linha: sistema.loc[    sistema["codigo_submercado"] == linha[4], "nome_submercado"    ].tolist()[0],   axis=1, )
        # Gera os vetores da dimensão do DF extraído do arquivo vazaof
        codigos_ordenados = cls._formata_dados_series(
            dados_uhes[0].to_numpy(), num_series, num_estagios
        )
        nomes_ordenados = cls._formata_dados_series(
            dados_uhes[1].to_numpy(), num_series, num_estagios
        )
        codigos_rees_ordenados = cls._formata_dados_series(
            dados_uhes[2].to_numpy(), num_series, num_estagios
        )
        nomes_rees_ordenados = cls._formata_dados_series(
            dados_uhes[3].to_numpy(), num_series, num_estagios
        )
        codigos_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[4].to_numpy(), num_series, num_estagios
        )
        nomes_submercados_ordenados = cls._formata_dados_series(
            dados_uhes[5].to_numpy(), num_series, num_estagios
        )
        datas = pd.date_range(
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            ),
            datetime(
                year=ano_inicio - 1,
                month=1,
                day=1,
            )
            + relativedelta(months=num_estagios - 1),
            freq="MS",
        )
        datas_ordenadas = np.repeat(datas, num_series * num_uhes)
        # Edita o DF e retorna
        vazaos_dados["codigo_usina"] = codigos_ordenados
        vazaos_dados["nome_usina"] = nomes_ordenados
        vazaos_dados["codigo_ree"] = codigos_rees_ordenados
        vazaos_dados["nome_ree"] = nomes_rees_ordenados
        vazaos_dados["codigo_submercado"] = codigos_submercados_ordenados
        vazaos_dados["nome_submercado"] = nomes_submercados_ordenados
        vazaos_dados["data"] = datas_ordenadas
        vazaos_dados["data_fim"] = [
            d + relativedelta(months=1) for d in datas_ordenadas
        ]
        vazaos_dados["estagio"] -= mes_inicio - 1
        vazaos_dados = vazaos_dados.loc[vazaos_dados["estagio"] > 0]
        vazaos_dados.drop(columns=["uhe"], inplace=True)
        print("vazaos_dados: ", vazaos_dados)
        return vazaos_dados[
            [
                "estagio",
                "data",
                "data_fim",
                "serie",
                "codigo_usina",
                "nome_usina",
                "codigo_ree",
                "nome_ree",
                "codigo_submercado",
                "nome_submercado",
                "valor",
            ]
        ]

    @classmethod
    def _resolve_enaa_forward_iteracao(
        cls, uow: AbstractUnitOfWork, it: int
    ) -> pd.DataFrame:
        logger = Log.configure_process_logger(
            uow._queue, Variable.ENA_ABSOLUTA.value, it
        )

        logger.info(f"Obtendo energias forward da it. {it}")
        with uow:
            arq_enavaz = uow.files.get_enavazf(it)
            if arq_enavaz is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de energia")
            arq_energiaf = uow.files.get_energiaf(it)
            if arq_energiaf is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de energia")
        if arq_enavaz is None:
            df_enavaz = pd.DataFrame()
        else:
            df_enavaz = (
                arq_enavaz.series
                if arq_enavaz.series is not None
                else pd.DataFrame()
            )
        if arq_energiaf is None:
            df_energia = pd.DataFrame()
        else:
            df_energia = (
                arq_energiaf.series
                if arq_energiaf.series is not None
                else pd.DataFrame()
            )
        if not df_enavaz.empty and not df_energia.empty:
            with uow:
                n_indiv = uow.files._numero_estagios_individualizados()
            df_ena = pd.concat(
                [
                    df_enavaz.loc[df_enavaz["estagio"] <= n_indiv],
                    df_energia.loc[df_energia["estagio"] > n_indiv],
                ],
                ignore_index=True,
            )
        else:
            df_ena = df_energia
        if not df_ena.empty:
            ena_it = cls._adiciona_dados_rees_forward(uow, df_ena)
            ena_it["iteracao"] = it
            return ena_it
        return None

    @classmethod
    def _resolve_enaa_forward(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        convergencia = cls._validate_data(
            cls._get_pmo(uow).convergencia, pd.DataFrame, "convergência"
        )
        #n_iters = convergencia["iteracao"].max()
        dger = cls._get_dger(uow)
        n_iters = dger.num_max_iteracoes
        df_completo = pd.DataFrame()
        n_procs = int(Settings().processors)
        with Pool(processes=n_procs) as pool:
            if n_procs > 1:
                if cls.logger is not None:
                    cls.logger.info("Paralelizando...")
            async_res = {
                it: pool.apply_async(
                    cls._resolve_enaa_forward_iteracao, (uow, it)
                )
                for it in range(1, n_iters + 1)
            }
            dfs = {it: r.get(timeout=3600) for it, r in async_res.items()}
        if cls.logger is not None:
            cls.logger.info("Compactando dados...")
        for _, df in dfs.items():
            df_completo = pd.concat([df_completo, df], ignore_index=True)
        return df_completo

    @classmethod
    def _resolve_qinc_forward_iteracao(
        cls, uow: AbstractUnitOfWork, it: int
    ) -> pd.DataFrame:
        logger = Log.configure_process_logger(
            uow.queue, Variable.VAZAO_INCREMENTAL.value, it
        )

        logger.info(f"Obtendo vazões forward da it. {it}")
        with uow:
            arq = uow.files.get_vazaof(it)
            if arq is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de vazão")
        vaz_it = (
            cls._adiciona_dados_uhes_forward(uow, arq.series)
            if arq is not None
            else pd.DataFrame()
        )
        if not vaz_it.empty:
            vaz_it["iteracao"] = it
            return vaz_it
        return None

    @classmethod
    def _resolve_qinc_forward(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        convergencia = cls._validate_data(
            cls._get_pmo(uow).convergencia, pd.DataFrame, "convergência"
        )
        #n_iters = convergencia["iteracao"].max()
        dger = cls._get_dger(uow)
        n_iters = dger.num_max_iteracoes
        #n_iters = 1
        df_completo = pd.DataFrame()
        n_procs = int(Settings().processors)
        with Pool(processes=n_procs) as pool:
            if n_procs > 1:
                if cls.logger is not None:
                    cls.logger.info("Paralelizando...")
            async_res = {
                it: pool.apply_async(
                    cls._resolve_qinc_forward_iteracao, (uow, it)
                )
                for it in range(1, n_iters + 1)
            }
            dfs = {ir: r.get(timeout=3600) for ir, r in async_res.items()}
        if cls.logger is not None:
            cls.logger.info("Compactando dados...")
        for _, df in dfs.items():
            df_completo = pd.concat([df_completo, df], ignore_index=True)
        return df_completo

    @classmethod
    def _resolve_enaa_backward_iteracao(
        cls, uow: AbstractUnitOfWork, it: int
    ) -> pd.DataFrame:
        logger = Log.configure_process_logger(
            uow._queue, Variable.ENA_ABSOLUTA.value, it
        )

        logger.info(f"Obtendo energias backward da it. {it}")
        with uow:
            arq_enavazb = uow.files.get_enavazb(it)
            if arq_enavazb is None:
                logger.error(
                    f"Falha na leitura de séries de enavaz da it {it}"
                )
            arq_energiab = uow.files.get_energiab(it)
            if arq_energiab is None:
                logger.error(
                    f"Falha na leitura de séries de energia da it {it}"
                )
                return None
        if arq_enavazb is not None:
            df_enavaz = (
                arq_enavazb.series
                if arq_enavazb.series is not None
                else pd.DataFrame()
            )
        else:
            df_enavaz = pd.DataFrame()
        df_energia = (
            arq_energiab.series
            if arq_energiab.series is not None
            else pd.DataFrame()
        )
        if not df_enavaz.empty and not df_energia.empty:
            with uow:
                n_indiv = uow.files._numero_estagios_individualizados()
            df_ena = pd.concat(
                [
                    df_enavaz.loc[df_enavaz["estagio"] <= n_indiv],
                    df_energia.loc[df_energia["estagio"] > n_indiv],
                ],
                ignore_index=True,
            )
        else:
            df_ena = df_energia
        ena_it = (
            cls._adiciona_dados_rees_backward(uow, df_ena)
            if not df_ena.empty
            else pd.DataFrame()
        )
        if not ena_it.empty:
            ena_it["iteracao"] = it
            return ena_it
        return None

    @classmethod
    def _resolve_enaa_backward(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        convergencia = cls._validate_data(
            cls._get_pmo(uow).convergencia, pd.DataFrame, "convergência"
        )
        n_iters = convergencia["iteracao"].max()
        dger = cls._get_dger(uow)
        n_iters = dger.num_max_iteracoes
        df_completo = pd.DataFrame()
        n_procs = int(Settings().processors)
        with Pool(processes=n_procs) as pool:
            if n_procs > 1:
                if cls.logger is not None:
                    cls.logger.info("Paralelizando...")
            async_res = {
                it: pool.apply_async(
                    cls._resolve_enaa_backward_iteracao, (uow, it)
                )
                for it in range(1, n_iters + 1)
            }
            dfs = {ir: r.get(timeout=3600) for ir, r in async_res.items()}
        if cls.logger is not None:
            cls.logger.info("Compactando dados...")
        for _, df in dfs.items():
            df_completo = pd.concat([df_completo, df], ignore_index=True)
        return df_completo

    @classmethod
    def _resolve_qinc_backward_iteracao(
        cls, uow: AbstractUnitOfWork, it: int
    ) -> pd.DataFrame:
        logger = Log.configure_process_logger(
            uow.queue, Variable.VAZAO_INCREMENTAL.value, it
        )
        logger.info(f"Obtendo vazões backward da it. {it}")
        with uow:
            arq = uow.files.get_vazaob(it)
        vaz_it = (
            cls._adiciona_dados_uhes_backward(uow, arq.series)
            if arq is not None
            else pd.DataFrame()
        )
        if not vaz_it.empty:
            vaz_it["iteracao"] = it
            return vaz_it
        return None

    @classmethod
    def _resolve_qinc_backward(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        convergencia = cls._validate_data(
            cls._get_pmo(uow).convergencia, pd.DataFrame, "convergência"
        )
        n_iters = convergencia["iteracao"].max()
        df_completo = pd.DataFrame()
        n_procs = int(Settings().processors)
        with Pool(processes=n_procs) as pool:
            if n_procs > 1:
                if cls.logger is not None:
                    cls.logger.info("Paralelizando...")
            async_res = {
                it: pool.apply_async(
                    cls._resolve_qinc_backward_iteracao, (uow, it)
                )
                for it in range(1, n_iters + 1)
            }
            dfs = {ir: r.get(timeout=3600) for ir, r in async_res.items()}
        if cls.logger is not None:
            cls.logger.info("Compactando dados...")
        for _, df in dfs.items():
            df_completo = pd.concat([df_completo, df], ignore_index=True)
        return df_completo

    @classmethod
    def _resolve_enaa_sf(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        with uow:
            arq_enavaz = uow.files.get_enavazs()
            if arq_enavaz is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de energia")
            arq_energias = uow.files.get_energias()
            if arq_energias is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de energia")
                raise RuntimeError()
        if arq_enavaz is not None:
            df_enavaz = (
                arq_enavaz.series
                if arq_enavaz.series is not None
                else pd.DataFrame()
            )
        else:
            df_enavaz = pd.DataFrame()
        df_energia = (
            arq_energias.series
            if arq_energias.series is not None
            else pd.DataFrame()
        )
        if not df_enavaz.empty and not df_energia.empty:
            with uow:
                n_indiv = uow.files._numero_estagios_individualizados()
            df_ena = pd.concat(
                [
                    df_enavaz.loc[df_enavaz["estagio"] <= n_indiv],
                    df_energia.loc[df_energia["estagio"] > n_indiv],
                ],
                ignore_index=True,
            )
        else:
            df_ena = df_energia
        enas = (
            cls._adiciona_dados_rees_sf(uow, df_ena)
            if df_ena is not None
            else pd.DataFrame()
        )
        return enas

    @classmethod
    def _resolve_qinc_sf(cls, uow: AbstractUnitOfWork) -> pd.DataFrame:
        with uow:
            arq = uow.files.get_vazaos()
            if arq is None:
                if cls.logger is not None:
                    cls.logger.error("Falha na leitura de séries de vazão")
        df = (
            cls._adiciona_dados_uhes_sf(uow, arq.series)
            if arq is not None
            else pd.DataFrame()
        )
        return df

    @classmethod
    def _get_cached_variable(
        cls,
        variable: Variable,
        step: Step,
        uow: AbstractUnitOfWork,
    ) -> pd.DataFrame:
        CACHING_FUNCTION_MAP: Dict[Tuple[Variable, Step], Callable] = {
            (Variable.ENA_ABSOLUTA, Step.FORWARD): cls._resolve_enaa_forward,
            (Variable.ENA_ABSOLUTA, Step.BACKWARD): cls._resolve_enaa_backward,
            (Variable.ENA_ABSOLUTA, Step.FINAL_SIMULATION): cls._resolve_enaa_sf,
            ( Variable.VAZAO_INCREMENTAL, Step.FORWARD): cls._resolve_qinc_forward,
            (  Variable.VAZAO_INCREMENTAL,    Step.BACKWARD ): cls._resolve_qinc_backward,
            ( Variable.VAZAO_INCREMENTAL,  Step.FINAL_SIMULATION ): cls._resolve_qinc_sf,
        }
        if cls.CACHED_SYNTHESIS.get((variable, step)) is None:
            cls.CACHED_SYNTHESIS[(variable, step)] = CACHING_FUNCTION_MAP[
                (variable, step)
            ](uow)
            
        return cls.CACHED_SYNTHESIS.get((variable, step), pd.DataFrame())

    @classmethod
    def _resolve_group(
        cls, group_col: List[str], df: pd.DataFrame
    ) -> pd.DataFrame:
        if not df.empty:
            cols = group_col + [
                c for c in cls.COMMON_COLUMNS if c in df.columns
            ]
            df_agrupado = df.groupby(cols).sum(numeric_only=True).reset_index()
            return df_agrupado[cols + ["valor"]]
        else:
            return df

    @classmethod
    def _apply_mlt_forward(
        cls,
        df: pd.DataFrame,
        df_mlt: pd.DataFrame,
        filter_col: Optional[str],
    ) -> pd.DataFrame:

        print("df: ", df)
        print("df_mlt: ", df_mlt)
        if filter_col is not None:
            df = df.sort_values(["iteracao", "estagio", filter_col, "serie"])
            df_mlt = df_mlt.sort_values(["estagio", filter_col])
        else:
            df = df.sort_values(["iteracao", "estagio", "serie"])
            df_mlt = df_mlt.sort_values(["estagio"])

        
        series = df["serie"].unique()
        num_series = len(series)
        estagios = df["estagio"].unique()
        iteracoes = df["iteracao"].unique()
        num_iteracoes = len(iteracoes)
        elements = df[filter_col].unique() if filter_col is not None else []

        
        df_mlts_elements = pd.DataFrame()
        for estagio in estagios:
            if len(elements) > 0 :
                for element in elements:
                    df_mlts_elements = pd.concat( [ df_mlts_elements,  df_mlt.loc[(df_mlt[filter_col] == element) & (df_mlt["estagio"] == estagio), "mlt" ], ],  ignore_index=True )
            else:
                df_mlts_elements = pd.concat(
                    [
                        df_mlts_elements,
                        df_mlt.loc[
                            (df_mlt["estagio"] == estagio),
                            "mlt",
                        ],
                    ],
                    ignore_index=True,
                )

        mlts_ordenadas = np.repeat(df_mlts_elements.to_numpy(), num_series)

        df["mlt"] = np.tile(mlts_ordenadas, num_iteracoes)
        df["valorMlt"] = df["valor"] / df["mlt"]
        df.replace([np.inf, -np.inf], 0, inplace=True)
        return df

    @classmethod
    def _apply_mlt_backward(
        cls,
        df: pd.DataFrame,
        df_mlt: pd.DataFrame,
        filter_col: Optional[str],
    ) -> pd.DataFrame:
        if filter_col is not None:
            df = df.sort_values(["estagio", filter_col, "serie", "abertura"])
            df_mlt = df_mlt.sort_values(["estagio", filter_col])
        else:
            df = df.sort_values(["estagio", "serie", "abertura"])
            df_mlt = df_mlt.sort_values(["estagio"])

        series = df["serie"].unique()
        num_series = len(series)
        estagios = df["estagio"].unique()
        aberturas = df["abertura"].unique()
        num_aberturas = len(aberturas)
        iteracoes = df["iteracao"].unique()
        num_iteracoes = len(iteracoes)
        elements = df[filter_col].unique() if filter_col is not None else []

        df_mlts_elements = pd.DataFrame()
        for estagio in estagios:
            if len(elements) > 0:
                for element in elements:
                    df_mlts_elements = pd.concat(
                        [
                            df_mlts_elements,
                            df_mlt.loc[
                                (df_mlt[filter_col] == element)
                                & (df_mlt["estagio"] == estagio),
                                "mlt",
                            ],
                        ],
                        ignore_index=True,
                    )
            else:
                df_mlts_elements = pd.concat(
                    [
                        df_mlts_elements,
                        df_mlt.loc[
                            (df_mlt["estagio"] == estagio),
                            "mlt",
                        ],
                    ],
                    ignore_index=True,
                )

        mlts_ordenadas = np.repeat(
            df_mlts_elements.to_numpy(), num_series * num_aberturas
        )
        df["mlt"] = np.tile(mlts_ordenadas, num_iteracoes)
        df["valorMlt"] = df["valor"] / df["mlt"]
        df.replace([np.inf, -np.inf], 0, inplace=True)
        return df

    @classmethod
    def _apply_mlt_sf(
        cls,
        df: pd.DataFrame,
        df_mlt: pd.DataFrame,
        filter_col: Optional[str],
    ) -> pd.DataFrame:
        if filter_col is not None:
            df = df.sort_values(["estagio", filter_col, "serie"])
            df_mlt = df_mlt.sort_values(["estagio", filter_col])
        else:
            df = df.sort_values(["estagio", "serie"])
            df_mlt = df_mlt.sort_values(["estagio"])

        series = df["serie"].unique()
        num_series = len(series)
        estagios = df["estagio"].unique()
        print("estagios: ", estagios)
        print("estagios: ", df_mlt["estagio"].unique())
        elements = df[filter_col].unique() if filter_col is not None else []

        df_mlts_elements = pd.DataFrame()
        for estagio in estagios:
            if len(elements) > 0:
                for element in elements:
                    df_mlts_elements = pd.concat(
                        [
                            df_mlts_elements,
                            df_mlt.loc[
                                (df_mlt[filter_col] == element)
                                & (df_mlt["estagio"] == estagio),
                                "mlt",
                            ],
                        ],
                        ignore_index=True,
                    )
            else:
                df_mlts_elements = pd.concat(
                    [
                        df_mlts_elements,
                        df_mlt.loc[
                            (df_mlt["estagio"] == estagio),
                            "mlt",
                        ],
                    ],
                    ignore_index=True,
                )

        mlts_ordenadas = np.repeat(df_mlts_elements.to_numpy(), num_series)
        df["mlt"] = mlts_ordenadas
        df["valorMlt"] = df["valor"] / df["mlt"]
        df.replace([np.inf, -np.inf], 0, inplace=True)
        return df

    @classmethod
    def _apply_mlt(
        cls,
        synthesis: ScenarioSynthesis,
        df: pd.DataFrame,
        uow: AbstractUnitOfWork,
    ) -> pd.DataFrame:
        # Descobre o valor em MLT
        df = df.copy()
        print("synthesis.variable: ", synthesis.variable)
        print("synthesis.spatial_resolution: ", synthesis.spatial_resolution)
        df_mlt = cls._get_cached_mlt(
            synthesis.variable,
            synthesis.spatial_resolution,
            uow,
        )
        FILTER_MAP = {
            SpatialResolution.USINA_HIDROELETRICA: "nome_usina",
            SpatialResolution.RESERVATORIO_EQUIVALENTE: "nome_ree",
            SpatialResolution.SUBMERCADO: "nome_submercado",
            SpatialResolution.SISTEMA_INTERLIGADO: None,
        }

        filter_col = FILTER_MAP[synthesis.spatial_resolution]
        # Aplica a conversão
        APPLY_MAP: Dict[Step, Callable] = {
            Step.FORWARD: cls._apply_mlt_forward,
            Step.FINAL_SIMULATION: cls._apply_mlt_sf,
            Step.BACKWARD: cls._apply_mlt_backward,
        }
        return APPLY_MAP[synthesis.step](df, df_mlt, filter_col)

    @classmethod
    def _resolve_spatial_resolution(
        cls, synthesis: ScenarioSynthesis, uow: AbstractUnitOfWork
    ) -> pd.DataFrame:
        RESOLUTION_MAP: Dict[SpatialResolution, List[str]] = {
            SpatialResolution.SISTEMA_INTERLIGADO: [],
            SpatialResolution.SUBMERCADO: ["nome_submercado"],
            SpatialResolution.RESERVATORIO_EQUIVALENTE: ["nome_ree"],
            SpatialResolution.USINA_HIDROELETRICA: ["nome_usina"],
        }
        df = cls._get_cached_variable(synthesis.variable, synthesis.step, uow)
        df = cls._resolve_group(
            RESOLUTION_MAP[synthesis.spatial_resolution], df
        )
        return cls._apply_mlt(synthesis, df, uow)

    @classmethod
    def _process_quantiles(
        cls, df: pd.DataFrame, quantiles: List[float]
    ) -> pd.DataFrame:
        group_cols = [
            col
            for col in df.columns.tolist()
            if col in cls.IDENTIFICATION_COLUMNS
        ]
        for q in quantiles:
            if q == 0:
                label = "min"
            elif q == 1:
                label = "max"
            elif q == 0.5:
                label = "median"
            else:
                label = f"p{int(100 * q)}"
            df_group = (
                df.groupby(group_cols)
                .quantile(q, numeric_only=True)
                .reset_index()
            )
            if "abertura" in group_cols:
                df_group["abertura"] = None
            df_group["cenario"] = label
            df = pd.concat([df, df_group], ignore_index=True)
        return df

    @classmethod
    def _process_mean(cls, df: pd.DataFrame) -> pd.DataFrame:
        group_cols = [
            col
            for col in df.columns.tolist()
            if col in cls.IDENTIFICATION_COLUMNS
        ]
        df = df.astype({"cenario": str})
        cenarios = df["cenario"].unique()
        cenarios = [c for c in cenarios if c not in ["min", "max", "median"]]
        cenarios = [c for c in cenarios if "p" not in c]
        df_mean = df.groupby(group_cols).mean(numeric_only=True).reset_index()
        df_std = df.groupby(group_cols).std(numeric_only=True).reset_index()
        if "abertura" in group_cols:
            df_mean["abertura"] = None
            df_std["abertura"] = None
        df_mean["cenario"] = "mean"
        df_std["cenario"] = "std"

        return pd.concat([df, df_mean, df_std], ignore_index=True)

    @classmethod
    def _postprocess(cls, df: pd.DataFrame):
        column_names = {
            "data": "dataInicio",
            "data_fim": "dataFim",
            "nome_usina": "usina",
            "nome_ree": "ree",
            "nome_submercado": "submercado",
            "serie": "cenario",
        }
        df.rename(
            columns={k: v for k, v in column_names.items() if k in df.columns},
            inplace=True,
        )
        # Calcula estatisticas
        df = cls._process_quantiles(df, [0.05 * i for i in range(21)])
        df = cls._process_mean(df)
        return df

    @classmethod
    def synthetize(cls, variables: List[str], uow: AbstractUnitOfWork):
        cls.logger = logging.getLogger("main")
        try:
            if len(variables) == 0:
                synthesis_variables = ScenarioSynthetizer._default_args()
            else:
                synthesis_variables = (
                    ScenarioSynthetizer._process_variable_arguments(variables)
                )
            valid_synthesis = ScenarioSynthetizer.filter_valid_variables(
                synthesis_variables, uow
            )
            if(len(valid_synthesis) == 0):
                cls.logger.error("Variavel invalida para sintese, por favor tentar alguma das variáveis abaixo:")
                cls.logger.error(cls.DEFAULT_SCENARIO_SYNTHESIS_ARGS)
            for s in valid_synthesis:
                filename = str(s)

                cls.logger.info(f"Realizando síntese de {filename}")
                df = cls._resolve_spatial_resolution(s, uow)
                if df is None:
                    continue
                elif isinstance(df, pd.DataFrame):
                    if df.empty:
                        cls.logger.info("Erro ao realizar a síntese")
                        continue
                # TODO - adicionar estatísticas ao postprocess
                df = cls._postprocess(df)
                with uow:
                    uow.export.synthetize_df(df, filename)
        except Exception as e:
            print_exc()
            cls.logger.error(str(e))
