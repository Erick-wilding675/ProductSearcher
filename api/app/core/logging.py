"""Logging estruturado (RNF-05).

TODO Fase 3: adicionar correlação por requisição (request id) via middleware.
"""

import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
