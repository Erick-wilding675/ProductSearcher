"""Cliente da API do Mercado Livre — busca a ficha técnica (attributes) por item ID.

A API exige access token (OAuth) desde 2024. Falhas de rede/HTTP não derrubam o
lote: retornam ``[]`` e logam. ``urlopen`` é injetável para teste.
"""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.mercadolibre.com/items/{item_id}?attributes=attributes"


def fetch_attributes(
    item_id: str,
    token: str,
    *,
    timeout: int = 15,
    urlopen: Callable = urllib.request.urlopen,
) -> list[dict]:
    """Retorna a lista de atributos do item (ou ``[]`` em caso de erro)."""
    request = urllib.request.Request(
        _ENDPOINT.format(item_id=item_id),
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("attributes", [])
    except urllib.error.HTTPError as exc:
        logger.warning("ML API retornou %s para %s", exc.code, item_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ML API falhou para %s: %s", item_id, exc)
    return []
