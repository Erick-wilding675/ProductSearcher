"""Lê a tabela `searches` e responde o que o código não responde: como as
pessoas realmente pedem, e onde a busca as deixa na mão.

Por que existe: a suíte de relevância é calibrada com consultas que **nós**
escrevemos. Isso mede a busca contra a nossa imaginação. `searches` (alimentada
pelo `SqlSearchLog` desde a Fase 5) guarda o que foi digitado de verdade, com o
que o `IntentParser` entendeu e quantos resultados voltaram — é a única régua
externa que temos. Este relatório transforma essa tabela em três respostas:

1. **O que volta vazio.** `result_count = 0` é falha visível: o usuário pediu e
   não recebeu nada. Cada consulta dessas é candidata direta a caso novo na
   suíte (`api/tests/test_relevance_use_cases.py`).
2. **O que o parser não entendeu.** `parsed_intent->>'category'` nulo significa
   que a consulta não caiu em nenhuma categoria — ou o vocabulário do
   `RuleBasedIntentParser` está curto, ou o catálogo não cobre o que pedem.
3. **Como o usuário descreve necessidade.** Consultas com "para"/"pra" são
   consultas de uso ("fone para academia"), não de produto conhecido. São
   exatamente as que a Fase 6 ataca, e o vocabulário real delas deve substituir
   o que inventamos nos casos de teste.

    python -m tools.search_insights              # relatório completo
    python -m tools.search_insights --limite 30  # mais linhas por seção

Somente leitura: não escreve nem apaga nada. Passo 1 da Fase 6 (ADR-010, D1).

Privacidade: `searches` guarda só o texto e o que o parser extraiu — sem usuário,
IP ou sessão (ver `app/search/log.py`). Ainda assim, o texto é digitado por
gente: trate a saída como dado de produto, não a cole em lugar público sem ler.
"""

import argparse
import os
from pathlib import Path

import sqlalchemy as sa

# Marcadores de consulta por necessidade. "para"/"pra" cobrem a forma dominante em
# pt-BR ("notebook para faculdade"); os demais pegam quem descreve a atividade sem
# a preposição. Heurística, não classificador — o objetivo é separar um punhado de
# consultas para leitura humana, não rotular o corpus.
_MARCADORES_DE_USO = ("para ", "pra ", "que sirva", "usar em", "usar no", "usar na")


def _sql_marcadores(coluna: str) -> str:
    return " or ".join(f"lower({coluna}) like '%{m}%'" for m in _MARCADORES_DE_USO)


def resumo(conn: sa.Connection) -> dict:
    """Números de cabeçalho: sem eles não dá para saber se o resto tem lastro."""
    linha = conn.execute(
        sa.text(
            "select count(*) as total, "
            "count(distinct lower(query_text)) as distintas, "
            "count(*) filter (where result_count = 0) as vazias, "
            "min(created_at) as inicio, max(created_at) as fim "
            "from searches"
        )
    ).one()
    return dict(linha._mapping)


def mais_frequentes(conn: sa.Connection, limite: int, so_vazias: bool = False) -> list:
    """Consultas por frequência. `so_vazias` isola as que não devolveram nada."""
    filtro = "where result_count = 0" if so_vazias else ""
    return conn.execute(
        sa.text(
            "select lower(query_text) as consulta, count(*) as vezes, "
            "round(avg(result_count)) as media_resultados "
            f"from searches {filtro} "
            "group by 1 order by vezes desc, consulta limit :limite"
        ),
        {"limite": limite},
    ).all()


def sem_categoria(conn: sa.Connection, limite: int) -> list:
    """Consultas em que o parser não identificou categoria — o ponto cego dele."""
    return conn.execute(
        sa.text(
            "select lower(query_text) as consulta, count(*) as vezes, "
            "round(avg(result_count)) as media_resultados "
            "from searches "
            "where parsed_intent->>'category' is null "
            "group by 1 order by vezes desc, consulta limit :limite"
        ),
        {"limite": limite},
    ).all()


def por_necessidade(conn: sa.Connection, limite: int) -> list:
    """Consultas de caso de uso, com o texto que sobrou para o FTS.

    `parsed_intent->>'text'` é o que de fato foi ao `plainto_tsquery`. Ver os dois
    lado a lado mostra o problema da Fase 6 em uma linha: o usuário pede "para
    edição de vídeo" e o que vai ao índice é "notebook edicao video" — palavras
    que ninguém escreve no título de um anúncio.
    """
    return conn.execute(
        sa.text(
            "select lower(query_text) as consulta, "
            "parsed_intent->>'text' as texto_fts, "
            "parsed_intent->>'category' as categoria, "
            "count(*) as vezes, round(avg(result_count)) as media_resultados "
            f"from searches where {_sql_marcadores('query_text')} "
            "group by 1, 2, 3 order by vezes desc, consulta limit :limite"
        ),
        {"limite": limite},
    ).all()


def _tabela(linhas, colunas: list[tuple[str, str, int]]) -> str:
    """Renderiza (rótulo, atributo, largura) — sem dependência de lib de tabela."""
    cab = "  ".join(f"{rotulo:<{larg}}" for rotulo, _, larg in colunas)
    out = [cab, "-" * len(cab)]
    for linha in linhas:
        out.append(
            "  ".join(
                f"{str(getattr(linha, attr, '') or ''):<{larg}}"[:larg] for _, attr, larg in colunas
            )
        )
    return "\n".join(out)


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=15, help="linhas por seção (padrão: 15)")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL.")

    engine = sa.create_engine(url, future=True)
    with engine.connect() as conn:
        cabecalho = resumo(conn)

        if not cabecalho["total"]:
            print(
                "A tabela `searches` está vazia.\n\n"
                "O registro só acontece por consulta que passa pelo `GET /search` com a\n"
                "dependency `get_search_log` (produção/dev com banco) — testes usam o\n"
                "`NullSearchLog` e não geram linha. Suba a API contra este banco e busque\n"
                "algumas vezes antes de rodar o relatório."
            )
            return

        print(
            f"{cabecalho['total']} buscas registradas "
            f"({cabecalho['distintas']} textos distintos), "
            f"{cabecalho['vazias']} sem resultado "
            f"({cabecalho['vazias'] / cabecalho['total']:.0%})\n"
            f"período: {cabecalho['inicio']:%d/%m/%Y} a {cabecalho['fim']:%d/%m/%Y}"
        )

        colunas = [
            ("consulta", "consulta", 44),
            ("vezes", "vezes", 6),
            ("média", "media_resultados", 6),
        ]

        print("\n== mais buscadas ==")
        print(_tabela(mais_frequentes(conn, args.limite), colunas))

        vazias = mais_frequentes(conn, args.limite, so_vazias=True)
        print("\n== voltaram vazias (candidatas a caso novo na suíte) ==")
        print(_tabela(vazias, colunas) if vazias else "  (nenhuma — a busca sempre devolveu algo)")

        cegas = sem_categoria(conn, args.limite)
        print("\n== parser não identificou categoria ==")
        print(_tabela(cegas, colunas) if cegas else "  (nenhuma — o parser categorizou tudo)")

        uso = por_necessidade(conn, args.limite)
        print("\n== consultas por necessidade (o alvo da Fase 6) ==")
        print(
            _tabela(
                uso,
                [
                    ("consulta", "consulta", 34),
                    ("vai ao FTS como", "texto_fts", 28),
                    ("categoria", "categoria", 11),
                    ("vezes", "vezes", 6),
                    ("média", "media_resultados", 6),
                ],
            )
            if uso
            else "  (nenhuma registrada ainda — o corpus atual é só de busca por produto)"
        )


if __name__ == "__main__":
    main()
