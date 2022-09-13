from abc import ABC, abstractmethod
from typing import Dict, Type
import pandas as pd  # type: ignore
import pathlib


class AbstractSynthesisRepository(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def synthetize_df(self, df: pd.DataFrame, filename: str) -> bool:
        pass


class ParquetSynthesisRepository(AbstractSynthesisRepository):
    def __init__(self, path: str):
        self.__path = path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.__path)

    def synthetize_df(self, df: pd.DataFrame, filename: str) -> bool:
        df.to_parquet(
            self.path.joinpath(filename + ".parquet.gzip"), compression="gzip"
        )
        pass


def factory(kind: str, *args, **kwargs) -> AbstractSynthesisRepository:
    mapping: Dict[str, Type[AbstractSynthesisRepository]] = {
        "PARQUET": ParquetSynthesisRepository
    }
    return mapping.get(kind)(*args, **kwargs)