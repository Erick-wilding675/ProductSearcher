"""Recorte público das specs: o que o cliente vê de `product_specs.attributes`.

O JSONB de specs guarda, além das specs de verdade, **carimbos da ingestão** —
`_labeling` (data e modelo do rotulador de `use_case`, ADR-010 D2) e o que vier
depois no mesmo espírito. São metadado de pipeline, não característica do produto:
não têm rótulo em `categories.json`, não servem para comparar dois produtos e não
significam nada para quem está comprando.

Sem este filtro eles vazam pelo contrato público: a página de produto renderiza
`Object.entries(product.specs)` e a comparação monta uma linha por chave presente
em qualquer um dos produtos — o carimbo viraria uma linha da tabela.

A convenção é o prefixo `_`, e ela é a mesma dos dois lados: o rotulador grava
`_labeling`, a API esconde tudo que começa com `_`.
"""

from typing import Any


def publicas(attributes: dict[str, Any] | None) -> dict[str, Any]:
    """Specs sem os carimbos internos da ingestão."""
    return {
        chave: valor for chave, valor in (attributes or {}).items() if not chave.startswith("_")
    }
