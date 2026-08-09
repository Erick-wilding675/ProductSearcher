"""Cliente da API do Mercado Livre para o seed-builder.

**Catálogo, não anúncio.** Os `external_id` do seed (`MLB45574031`) são ids de
*produto de catálogo*. O endpoint `/items/{id}` — que este módulo usava — devolve
**404** para todos eles; quem responde é `/products/{id}`. Era por isso que o
enriquecimento nunca preencheu nada e as specs vinham só do `title_parser`.

O que cada endpoint entrega (verificado em 2026-08-09, token de aplicação):

| Endpoint | Serve para |
| --- | --- |
| `/products/{id}` | `name` limpo, `short_description`, ficha técnica |
| `/products/{id}/items` | as ofertas reais do produto (preço + vendedor) |
| `/users/{id}` | nome e permalink da loja |

`/items/{id}` e `/sites/MLB/search` respondem **403** para token de aplicação —
não há como ampliar o catálogo por busca; dependemos do CSV já coletado.

Falhas de rede/HTTP nunca derrubam o lote: devolvem vazio e logam. `urlopen` é
injetável para teste.
"""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mercadolibre.com"


class MLClient:
    """Acesso somente-leitura à API do ML, tolerante a falha."""

    def __init__(
        self,
        token: str,
        *,
        timeout: int = 15,
        urlopen: Callable = urllib.request.urlopen,
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._urlopen = urlopen

    def _get(self, path: str) -> dict | None:
        """GET autenticado. Devolve ``None`` em qualquer falha (404 inclusive)."""
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        try:
            with self._urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # 404 é rotina: produto despublicado desde a coleta. Não polui o log.
            if exc.code != 404:
                logger.warning("ML API %s em %s", exc.code, path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ML API falhou em %s: %s", path, exc)
        return None

    def product(self, product_id: str) -> dict | None:
        """Ficha do produto de catálogo. ``None`` se despublicado ou fora do ar."""
        return self._get(f"/products/{product_id}")

    def product_items(self, product_id: str) -> list[dict]:
        """Anúncios que vendem esse produto — uma oferta por vendedor."""
        payload = self._get(f"/products/{product_id}/items")
        return (payload or {}).get("results", [])

    def user(self, user_id: str | int) -> dict | None:
        """Vendedor: usado para o nome e o permalink da loja."""
        return self._get(f"/users/{user_id}")


def _atributo(product: dict, *ids: str) -> str | None:
    """Primeiro atributo preenchido entre os ids dados, na ordem de preferência."""
    por_id = {a.get("id"): a.get("value_name") for a in product.get("attributes") or []}
    for atributo_id in ids:
        valor = (por_id.get(atributo_id) or "").strip()
        if valor:
            return valor
    return None


def product_fields(product: dict) -> dict:
    """Extrai de `/products/{id}` os campos que viram colunas e **identidade**.

    `catalog_parent_id` e `catalog_sku` resolvem quem é o mesmo produto, e a
    resposta vem da fonte em vez de heurística nossa:

    - variantes de cor compartilham `parent_id` — os cinco "Dapon H02D" do seed
      têm todos `MLB24117256` como pai;
    - produtos realmente diferentes têm pais diferentes mesmo com marca e modelo
      iguais — os "IdeaPad Slim 3 15IRH10" i5 e i7, SKUs `83NS0002BR` e
      `83NS0004BR`.

    `ALPHANUMERIC_MODEL` é o SKU do fabricante: o desempate curto e legível para o
    slug quando marca+modelo colidem. Ver ADR-0009.

    O `name` do catálogo é mais limpo que o título de anúncio, mas quem decide se
    ele substitui o `name` coletado é o `enrich`, que sabe o que já existe.
    """
    return {
        "catalog_name": (product.get("name") or "").strip() or None,
        "model": _atributo(product, "MODEL", "DETAILED_MODEL", "ALPHANUMERIC_MODEL"),
        "description": ((product.get("short_description") or {}).get("content") or "").strip()
        or None,
        # Identidade — ver `_atributo` e o ADR-0009.
        "catalog_parent_id": (product.get("parent_id") or "").strip() or None,
        "catalog_sku": _atributo(product, "ALPHANUMERIC_MODEL", "DETAILED_MODEL"),
    }
