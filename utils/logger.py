import logging
import sys
from pathlib import Path


def setup_logger(log_file):
    """Logger con salida a consola (INFO) y archivo (DEBUG)."""
    logger = logging.getLogger("guadalajara")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # ya configurado

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Consola
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Archivo
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
