"""Rotula `use_case` no catálogo com um LLM — **offline**, na ingestão.

Passo 2 da Fase 6 (ADR-010 D2). A ideia central: a melhor aplicação de LLM neste
projeto não é responder o usuário, é **preparar o dado** para que o caminho
determinístico consiga responder. Depois deste passo, "notebook para jogos" é
atendido pelo filtro JSONB que já existe (RF-12) — **zero IA em runtime**, zero
latência, zero custo por request.

Guardas, todas exigidas pelo ADR:

- **Conjunto fechado.** Os rótulos permitidos saem de `categories.json` e entram
  no schema da resposta. Rótulo fora da lista é rejeitado por `validate_specs`
  antes de chegar ao banco (`data_type: enum_multi`).
- **Nada de inventar atributo.** O prompt recebe só nome, modelo, descrição e as
  specs que **já estão no banco**. O LLM classifica o que existe; não completa
  ficha técnica.
- **Idempotente e carimbado**, como o `enrich.py` (ADR-0009 D2): o resultado fica
  em `attributes._labeling` (data + modelo), e reexecutar só tenta o que faltou.
- **Batch API**: metade do preço, e a latência não importa num passo offline.

Uso:

    python -m tools.seedbuilder.label_use_cases --dry-run   # monta e mostra, não envia
    python -m tools.seedbuilder.label_use_cases --submit    # envia o lote
    python -m tools.seedbuilder.label_use_cases --collect <batch_id>   # grava o resultado

O envio e a coleta são comandos separados de propósito: um lote pode levar até
24h, e ninguém precisa manter o processo vivo esperando.
"""

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from ingestion.pipeline import SEED_DIR
from ingestion.validate import read_categories, validate_specs

logger = logging.getLogger(__name__)

MODELO = "claude-opus-5"

# Specs que descrevem o produto para o classificador. Não é a lista inteira do
# schema: `bluetooth` e `screen_in` não ajudam a decidir uso e só gastam token.
SPECS_RELEVANTES = (
    "cpu", "gpu", "ram_gb", "storage_gb", "storage_type", "weight_kg", "touchscreen",
    "type", "anc", "battery_h", "microphone", "water_resistant",
)  # fmt: skip

INSTRUCAO = """Você classifica produtos de um catálogo brasileiro por CASO DE USO.

Receberá a ficha de um produto. Devolva os rótulos, do conjunto fechado abaixo,
que descrevem para que este produto de fato serve.

Regras:
- Use SOMENTE os rótulos da lista. Nunca invente rótulo.
- Baseie-se nas specs, não no marketing do título. Um anúncio que diz "gamer"
  mas não tem GPU dedicada não é `jogos`.
- Rotule por adequação real, não por possibilidade. Quase todo notebook "pode"
  ser usado para estudo; marque `estudo` quando o produto for adequado a isso —
  não quando for apenas possível.
- Vários rótulos são normais. Nenhum rótulo também é resposta válida: devolva
  lista vazia se a ficha não sustentar nenhum.
- Não deduza spec ausente. Se não há peso, não conclua nada sobre portabilidade.
"""


def rotulos_por_categoria(seed_dir: Path = SEED_DIR) -> dict[str, list[str]]:
    """Conjunto fechado de rótulos por categoria, lido do `categories.json`.

    Fonte única: o prompt, o schema da resposta e a validação leem daqui. Assim
    mexer no `categories.json` não deixa o rotulador para trás.
    """
    permitidos = {}
    for categoria in read_categories(seed_dir):
        for atributo in categoria.attributes:
            if atributo.attribute_key == "use_case":
                permitidos[categoria.slug] = list(atributo.allowed_values or [])
    return permitidos


def produtos_para_rotular(conn: sa.Connection, refazer: bool = False) -> list[dict[str, Any]]:
    """Fichas do banco. Sem `refazer`, pula quem já tem `use_case` gravado."""
    linhas = conn.execute(
        sa.text(
            "select p.id, p.name, p.model, p.description, c.slug as categoria, "
            "coalesce(ps.attributes, '{}'::jsonb) as attributes "
            "from products p "
            "join categories c on c.id = p.category_id "
            "left join product_specs ps on ps.product_id = p.id "
            "order by p.slug"
        )
    ).all()

    fichas = []
    for linha in linhas:
        atributos = linha.attributes or {}
        if not refazer and atributos.get("use_case"):
            continue
        fichas.append(
            {
                "id": str(linha.id),
                "categoria": linha.categoria,
                "name": linha.name,
                "model": linha.model,
                # A descrição do marketplace é longa e repetitiva; o começo já traz
                # o que importa e o corte segura o custo do lote.
                "description": (linha.description or "")[:1200],
                "specs": {k: v for k, v in atributos.items() if k in SPECS_RELEVANTES},
            }
        )
    return fichas


def monta_requisicao(ficha: dict[str, Any], permitidos: list[str]) -> dict[str, Any]:
    """Uma entrada do lote. `custom_id` é o id do produto — a volta é por chave."""
    corpo = {
        "nome": ficha["name"],
        "modelo": ficha["model"],
        "descricao": ficha["description"],
        "specs": ficha["specs"],
    }
    return {
        "custom_id": ficha["id"],
        "params": {
            "model": MODELO,
            "max_tokens": 1024,
            "system": INSTRUCAO + "\nRótulos permitidos: " + ", ".join(permitidos),
            "messages": [
                {"role": "user", "content": json.dumps(corpo, ensure_ascii=False, indent=2)}
            ],
            # O schema fecha o conjunto no próprio contrato da resposta: o modelo
            # não tem por onde devolver rótulo fora da lista. `validate_specs`
            # continua conferindo — schema é a primeira guarda, não a única.
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "use_case": {
                                "type": "array",
                                "items": {"type": "string", "enum": permitidos},
                            }
                        },
                        "required": ["use_case"],
                        "additionalProperties": False,
                    },
                }
            },
        },
    }


def _cliente():
    """Importa o SDK só quando vai usar — `--dry-run` roda sem a dependência."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise SystemExit(
            "SDK ausente. Instale com: pip install anthropic\n"
            "(fica em dependência opcional: a ingestão não precisa dele)"
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Defina ANTHROPIC_API_KEY no worker/.env ou no ambiente.")
    return anthropic.Anthropic()


def submete(requisicoes: list[dict[str, Any]]) -> str:
    """Envia o lote e devolve o id para a coleta posterior."""
    lote = _cliente().messages.batches.create(requests=requisicoes)
    return lote.id


def coleta(batch_id: str) -> dict[str, list[str]]:
    """Resultados por id de produto. Erro em um item não derruba o lote.

    Os resultados chegam em qualquer ordem — a volta é por `custom_id`, nunca por
    posição.
    """
    cliente = _cliente()
    lote = cliente.messages.batches.retrieve(batch_id)
    if lote.processing_status != "ended":
        raise SystemExit(f"Lote ainda em {lote.processing_status!r} — tente mais tarde.")

    rotulos: dict[str, list[str]] = {}
    for item in cliente.messages.batches.results(batch_id):
        if item.result.type != "succeeded":
            logger.warning("Produto %s: resultado %s", item.custom_id, item.result.type)
            continue
        texto = next((b.text for b in item.result.message.content if b.type == "text"), "")
        try:
            rotulos[item.custom_id] = json.loads(texto)["use_case"]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Produto %s: resposta ilegível (%.80s)", item.custom_id, texto)
    return rotulos


def grava(conn: sa.Connection, rotulos: dict[str, list[str]], schemas: dict) -> dict[str, int]:
    """Escreve os rótulos válidos em `product_specs.attributes`.

    Rótulo que não passa em `validate_specs` é descartado com log — a política
    "rejeita, loga e segue" do ADR-0005 D6, aplicada a dado vindo de LLM.
    """
    contagens = {"gravados": 0, "rejeitados": 0, "vazios": 0}
    for produto_id, valores in rotulos.items():
        if not valores:
            contagens["vazios"] += 1
            continue

        categoria = conn.execute(
            sa.text(
                "select c.slug from products p join categories c on c.id = p.category_id "
                "where p.id::text = :id"
            ),
            {"id": produto_id},
        ).scalar()
        erros = validate_specs({"use_case": valores}, schemas.get(categoria, []))
        if erros:
            logger.warning("Produto %s rejeitado: %s", produto_id, "; ".join(erros))
            contagens["rejeitados"] += 1
            continue

        carimbo = {
            "use_case": valores,
            "_labeling": {"data": str(date.today()), "modelo": MODELO},
        }
        conn.execute(
            sa.text(
                "update product_specs set attributes = attributes || cast(:novo as jsonb) "
                "where product_id::text = :id"
            ),
            {"novo": json.dumps(carimbo), "id": produto_id},
        )
        contagens["gravados"] += 1
    return contagens


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="monta o lote e mostra, não envia")
    parser.add_argument("--submit", action="store_true", help="envia o lote e imprime o id")
    parser.add_argument("--collect", metavar="BATCH_ID", help="coleta e grava o resultado")
    parser.add_argument("--refazer", action="store_true", help="rotula também quem já tem rótulo")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL.")
    engine = sa.create_engine(url, future=True)

    categorias = read_categories(SEED_DIR)
    schemas = {c.slug: c.attributes for c in categorias}

    if args.collect:
        rotulos = coleta(args.collect)
        with engine.begin() as conn:
            print("resultado:", grava(conn, rotulos, schemas))
        return

    permitidos = rotulos_por_categoria()
    with engine.connect() as conn:
        fichas = produtos_para_rotular(conn, refazer=args.refazer)

    requisicoes = [
        monta_requisicao(f, permitidos[f["categoria"]])
        for f in fichas
        if f["categoria"] in permitidos
    ]
    print(f"{len(requisicoes)} produtos a rotular (modelo {MODELO}, Batch API)")
    for slug, lista in permitidos.items():
        print(f"   {slug}: {', '.join(lista)}")

    if not requisicoes:
        print("\nNada a fazer — todos já têm rótulo. Use --refazer para refazer.")
        return

    if args.submit:
        print("\nlote enviado:", submete(requisicoes))
        print("Colete depois com --collect <id>.")
        return

    exemplo = requisicoes[0]
    print(f"\n(dry-run — nada enviado)\nExemplo de ficha enviada ({exemplo['custom_id']}):")
    print(exemplo["params"]["messages"][0]["content"][:700])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
