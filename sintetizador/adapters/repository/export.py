from abc import ABC, abstractmethod
from typing import Dict, Type
import pandas as pd  # type: ignore
import pyarrow.parquet as pq
import pathlib


class AbstractExportRepository(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def synthetize_df(self, df: pd.DataFrame, filename: str) -> bool:
        pass


class ParquetExportRepository(AbstractExportRepository):
    def __init__(self, path: str):
        self.__path = path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.__path)

    def synthetize_df(self, df: pd.DataFrame, filename: str) -> bool:
        pq.write_table(
            df,
            self.path.joinpath(filename + ".parquet.gzip"),
            compression="gzip",
            flavor="spark",
            coerce_timestamps="ms",
        )
        return True


class CSVExportRepository(AbstractExportRepository):
    def __init__(self, path: str):
        self.__path = path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.__path)

    def synthetize_df(self, df: pd.DataFrame, filename: str) -> bool:
        df.to_csv(self.path.joinpath(filename + ".csv"), index=False)
        return True


def factory(kind: str, *args, **kwargs) -> AbstractExportRepository:
    mapping: Dict[str, Type[AbstractExportRepository]] = {
        "PARQUET": ParquetExportRepository,
        "CSV": CSVExportRepository,
    }
    kind = kind.upper()
    if kind not in mapping.keys():
        msg = f"Formato de síntese: {kind} não suportado"
        raise ValueError(msg)
    return mapping.get(kind, ParquetExportRepository)(*args, **kwargs)
