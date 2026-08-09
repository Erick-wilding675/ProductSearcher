"""Re-deriva campos ausentes do seed já baixado, usando o mesmo `title_parser`.

Por que existe: o seed em `seed/products/*.yaml` é a SAÍDA do `build_seed.py`, que
fala com a API do Mercado Livre. Quando o `title_parser` melhora, o certo seria
regerar — mas isso exige credencial e refaz a coleta inteira, e os títulos já
estão salvos no próprio YAML.

Este script aplica as MESMAS funções do parser sobre os títulos já coletados e
preenche só o que está faltando. Nada é inventado: tudo sai do título do anúncio,
e campos já preenchidos nunca são sobrescritos.

Uso (idempotente — rodar duas vezes não muda nada na segunda):

    python -m tools.seedbuilder.backfill            # aplica
    python -m tools.seedbuilder.backfill --dry-run  # só relata
"""

import argparse
from pathlib import Path
from typing import Any

import yaml

from tools.seedbuilder.title_parser import extract_brand, parse_title

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "products"


def backfill_produto(produto: dict[str, Any]) -> list[str]:
    """Preenche marca/specs ausentes a partir do título. Devolve o que mudou."""
    mudancas: list[str] = []
    categoria = produto.get("category") or ""
    titulo = produto.get("name") or ""

    if not (produto.get("brand") or "").strip():
        marca = extract_brand(categoria, titulo)
        if marca:
            produto["brand"] = marca
            mudancas.append(f"brand={marca}")

    specs = produto.get("specs") or {}
    derivados = parse_title(categoria, titulo)
    for chave, valor in derivados.items():
        # Só o que falta: um valor vindo da API do marketplace é melhor que um
        # inferido do título e não deve ser sobrescrito.
        if chave not in specs:
            specs[chave] = valor
            mudancas.append(f"{chave}={valor}")

    if specs:
        produto["specs"] = specs

    return mudancas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="não grava, só relata")
    args = parser.parse_args()

    total_produtos = 0
    total_alterados = 0

    for caminho in sorted(SEED_DIR.glob("*.yaml")):
        produtos = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
        alterados = 0

        for produto in produtos:
            total_produtos += 1
            if backfill_produto(produto):
                alterados += 1

        total_alterados += alterados
        print(f"{caminho.name}: {alterados}/{len(produtos)} produtos completados")

        if not args.dry_run and alterados:
            caminho.write_text(
                yaml.safe_dump(produtos, allow_unicode=True, sort_keys=False, width=100),
                encoding="utf-8",
            )

    sufixo = " (dry-run, nada gravado)" if args.dry_run else ""
    print(f"total: {total_alterados}/{total_produtos} produtos completados{sufixo}")


if __name__ == "__main__":
    main()
