from typing import Tuple, Optional, List
from os.path import isfile
from os import listdir
from sintetizador.utils.terminal import run_terminal_retry
import time
import subprocess
import platform

TIMEOUT_DEFAULT = 10.0


async def converte_codificacao(path: str, script: str):
    if platform.system() == "Windows":
        return
    _, out = await run_terminal_retry([f"file -i {path}"])
    cod = out.split("charset=")[1].strip()
    if "unknown" in cod:
        cod = "ISO-8859-1"
    if all([cod != "utf-8", cod != "us-ascii", cod != "binary"]):
        cod = cod.upper()
        c, _ = await run_terminal_retry([f"{script}" + f" {path} {cod}"])
