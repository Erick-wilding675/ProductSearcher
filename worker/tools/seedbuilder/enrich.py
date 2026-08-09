"""Enriquece o seed já coletado com a ficha técnica do Mercado Livre.

Irmão do `backfill.py` — aquele re-deriva do **título**, este busca na **API**.
Preenche o que o título nunca teria: `model`, `description`, specs completas,
as ofertas concorrentes e a URL da loja.

Por que existe em vez de regerar pelo `build_seed.py`: regerar exigiria o CSV
original do Apify e refaria a coleta inteira. Os ids de catálogo já estão no
seed versionado, então dá para enriquecer no lugar — e reexecutar quantas vezes
quiser.

**Idempotente e conservador.** Nunca sobrescreve valor existente; guarda o
resultado de cada consulta em `_enrichment` (data e status), então reexecutar só
tenta de novo o que faltou. Produto despublicado (404) fica marcado como `stale`
e mantém o dado que veio do título — sem apagar nada.

Uso:

    python -m tools.seedbuilder.enrich --dry-run   # relata, não grava
    python -m tools.seedbuilder.enrich             # aplica
    python -m tools.seedbuilder.enrich --retry-stale  # tenta os 404 de novo
"""

import argparse
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tools.seedbuilder import mapping
from tools.seedbuilder.ml_api import MLClient, product_fields

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "products"

# Página de catálogo do produto (onde o comprador escolhe o vendedor).
CATALOGO_URL = "https://www.mercadolivre.com.br/p"

# Pausa entre chamadas: a API do ML tolera bem esse ritmo e o lote inteiro são
# poucas centenas de produtos. Ser educado sai mais barato que tomar 429.
PAUSA_S = 0.15


def _marca_enriquecimento(produto: dict, status: str) -> None:
    """Carimba a procedência: o que foi de 1ª mão (API) e o que não deu.

    `identity` registra que **perguntamos** pela identidade — e não que a fonte a
    tinha. Alguns produtos de catálogo não têm pai (são o topo da família), e sem
    essa distinção eles seriam reconsultados para sempre.
    """
    produto["enrichment"] = {
        "status": status,
        "date": date.today().isoformat(),
        "identity": True,
    }
    produto.pop("_enrichment", None)  # nome antigo, de antes da identidade


def _marcado(produto: dict) -> dict:
    """Lê o carimbo, aceitando o nome antigo (`_enrichment`) de rodadas passadas."""
    return produto.get("enrichment") or produto.get("_enrichment") or {}


def _ja_tentado(produto: dict, *, retry_stale: bool) -> bool:
    marca = _marcado(produto)
    if marca.get("status") == "ok":
        # Rodadas anteriores ao ADR-0009 não perguntaram pela identidade; essas
        # valem reconsultar uma vez.
        return bool(marca.get("identity"))
    return bool(marca) and not retry_stale


def preenche_urls_faltantes(produto: dict) -> int:
    """Dá URL às ofertas que não têm, sem chamar a API. Devolve quantas preencheu.

    Oferta sem URL vira um "Ver oferta" quebrado na tela de produto. A página de
    catálogo (`/p/{id}`) é onde o comprador escolhe entre os vendedores — é o
    destino certo, e o endereço é derivável do id que já temos.
    """
    pid = produto.get("external_id")
    if not pid:
        return 0

    destino = f"{CATALOGO_URL}/{pid}"
    preenchidas = 0
    for oferta in produto.get("offers") or []:
        if not (oferta.get("url") or "").strip():
            oferta["url"] = destino
            preenchidas += 1
    return preenchidas


def enriquece_produto(produto: dict, client: MLClient) -> list[str]:
    """Busca na API e preenche o que falta. Devolve o que mudou."""
    mudancas: list[str] = []
    pid = produto.get("external_id")
    categoria = produto.get("category") or ""

    ficha = client.product(pid) if pid else None
    if ficha is None:
        # Despublicado desde a coleta. Mantém o que o título deu (ADR-0009 D4).
        _marca_enriquecimento(produto, "stale")
        return mudancas

    campos = product_fields(ficha)

    # Identidade: sempre da API, mesmo que já exista — é ela que manda (ADR-0009).
    for chave in ("catalog_parent_id", "catalog_sku"):
        if campos[chave] and produto.get(chave) != campos[chave]:
            produto[chave] = campos[chave]
            mudancas.append(chave)

    if not (produto.get("model") or "").strip() and campos["model"]:
        produto["model"] = campos["model"]
        mudancas.append("model")

    if not (produto.get("description") or "").strip() and campos["description"]:
        produto["description"] = campos["description"]
        mudancas.append("description")

    specs = produto.get("specs") or {}
    for chave, valor in mapping.map_attributes(categoria, ficha.get("attributes") or []).items():
        # A API é fonte de 1ª mão, mas o que já está no seed pode ter vindo dela
        # numa rodada anterior. Só preenchemos buraco — nunca sobrescrevemos.
        if chave not in specs:
            specs[chave] = valor
            mudancas.append(f"specs.{chave}")
    if specs:
        produto["specs"] = specs

    if _enriquece_ofertas(produto, ficha, client, pid):
        mudancas.append("offers")

    _marca_enriquecimento(produto, "ok")
    return mudancas


def _enriquece_ofertas(produto: dict, ficha: dict, client: MLClient, pid: str) -> bool:
    """Acrescenta as ofertas concorrentes do catálogo (uma por vendedor).

    O seed trazia **uma** oferta por produto (a linha do CSV), o que deixava o
    "melhor valor" da comparação sem com quem comparar. `/products/{id}/items`
    devolve os anúncios que vendem o mesmo produto.

    Mais de uma oferta já gravada significa que uma rodada anterior fez isto. Como
    cada produto custa 1 chamada de anúncios + 1 por vendedor, pular o que já está
    pronto é a diferença entre segundos e minutos no lote inteiro.
    """
    ofertas = produto.get("offers") or []
    sem_url = preenche_urls_faltantes(produto)

    if len(ofertas) > 1:
        return bool(sem_url)

    anuncios = client.product_items(pid)
    if not anuncios:
        return bool(sem_url)

    permalink = (ficha.get("permalink") or "").strip() or f"{CATALOGO_URL}/{pid}"
    lojas_existentes = {(o.get("store") or "").strip().lower() for o in ofertas}
    novas = 0

    for anuncio in anuncios:
        preco = anuncio.get("price")
        vendedor = anuncio.get("seller_id")
        if preco is None or not vendedor:
            continue

        perfil = client.user(vendedor) or {}
        nome = (perfil.get("nickname") or "").strip()
        if not nome or nome.lower() in lojas_existentes:
            continue

        ofertas.append(
            {
                "store": nome,
                # `permalink` do vendedor vira a URL da loja no nosso catálogo.
                "store_url": perfil.get("permalink") or None,
                "price": str(preco),
                "currency": anuncio.get("currency_id") or "BRL",
                "url": permalink,
            }
        )
        lojas_existentes.add(nome.lower())
        novas += 1

    produto["offers"] = ofertas
    return bool(novas or sem_url)


def main() -> None:
    from tools.seedbuilder.config import load_env
    from tools.seedbuilder.ml_auth import access_token_from_env

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="não grava, só relata")
    parser.add_argument("--retry-stale", action="store_true", help="tenta de novo os que deram 404")
    parser.add_argument("--limit", type=int, help="processa só os N primeiros (para testar)")
    args = parser.parse_args()

    load_env()
    client = MLClient(access_token_from_env())

    totais: dict[str, Any] = {"produtos": 0, "enriquecidos": 0, "pulados": 0, "stale": 0}

    for caminho in sorted(SEED_DIR.glob("*.yaml")):
        produtos = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
        alterados = 0

        for indice, produto in enumerate(produtos):
            if args.limit and indice >= args.limit:
                break
            totais["produtos"] += 1

            # Barato e sem rede: roda para todo mundo, inclusive o que já foi feito.
            if preenche_urls_faltantes(produto):
                alterados += 1

            if _ja_tentado(produto, retry_stale=args.retry_stale):
                totais["pulados"] += 1
                continue

            if enriquece_produto(produto, client):
                alterados += 1
                totais["enriquecidos"] += 1
            if (produto.get("_enrichment") or {}).get("status") == "stale":
                totais["stale"] += 1
            time.sleep(PAUSA_S)

        print(f"{caminho.name}: {alterados}/{len(produtos)} enriquecidos")
        if not args.dry_run:
            caminho.write_text(
                yaml.safe_dump(produtos, allow_unicode=True, sort_keys=False, width=100),
                encoding="utf-8",
            )

    sufixo = " (dry-run, nada gravado)" if args.dry_run else ""
    print(
        f"total: {totais['enriquecidos']} enriquecidos, {totais['stale']} despublicados, "
        f"{totais['pulados']} já feitos, de {totais['produtos']}{sufixo}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
