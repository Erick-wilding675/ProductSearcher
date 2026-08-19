"""FTS insensível a acento (configuração `portuguese_unaccent`)

Consulta sem acento não casava texto com acento: `to_tsvector('portuguese', …)`
**não** dobra acento, e a extensão `unaccent` não estava instalada. Como o
`plainto_tsquery` combina os termos com AND (ADR-0007 D2.1), bastava um termo sem
acento para zerar a consulta inteira — "notebook para trabalho no escritorio"
virava `'notebook' & 'trabalh' & 'escritori'`, e `escritori` casava nada, embora
"escritório" apareça em 15 produtos.

Medido na Fase 6 (ADR-010, D1): dobrar acento leva a cobertura@5 de 27% para 55%
e a precisão média@5 de 16% para 36%, **sem IA nenhuma**.

O `unaccent` entra como **dicionário da configuração**, não como a função
`unaccent(text)` — esta é STABLE e por isso proibida em coluna gerada. Já
`to_tsvector(regconfig, text)` é IMMUTABLE mesmo quando a configuração dobra
acento, que é o caminho documentado para este caso.

A coluna gerada é **recriada** (drop + add) em vez de alterada: `ALTER COLUMN …
SET EXPRESSION` só existe a partir do PG17, e o dev local roda PG16
(`pgvector/pgvector:pg16`). Recriar funciona nos dois.

Revision ID: d2e4f6a8b0c1
Revises: c1a2b3d4e5f6
Create Date: 2026-08-19 14:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e4f6a8b0c1"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A configuração vive em `public` e é referenciada **qualificada** em todo lugar.
# Sem qualificar, o nome resolveria pelo `search_path` de quem consulta — e o do
# Supabase (`"$user", public, extensions`) não é o do Postgres do docker.
CONFIG = "public.portuguese_unaccent"

_EXPRESSAO = (
    f"to_tsvector('{CONFIG}', "
    "coalesce(name, '') || ' ' || coalesce(model, '') || ' ' || coalesce(description, ''))"
)


def upgrade() -> None:
    # `unaccent` cai em `extensions` no Supabase e em `public` no docker; os dois
    # estão no search_path, então o nome nu resolve no ALTER MAPPING abaixo.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    op.execute(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {CONFIG}")
    op.execute(f"CREATE TEXT SEARCH CONFIGURATION {CONFIG} (COPY = pg_catalog.portuguese)")
    # Ordem importa: `unaccent` primeiro tira o acento, `portuguese_stem` depois
    # reduz ao radical. Invertido, o stem receberia a forma acentuada e o
    # unaccent não teria mais o que dobrar.
    op.execute(
        f"ALTER TEXT SEARCH CONFIGURATION {CONFIG} "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem"
    )

    # A coluna é GERADA: recriá-la reindexa os 235 produtos sem passo de backfill.
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_column("products", "search_vector")
    op.execute(
        "ALTER TABLE products ADD COLUMN search_vector tsvector "
        f"GENERATED ALWAYS AS ({_EXPRESSAO}) STORED"
    )
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_column("products", "search_vector")
    op.execute(
        "ALTER TABLE products ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS ("
        "to_tsvector('portuguese', "
        "coalesce(name, '') || ' ' || coalesce(model, '') || ' ' || coalesce(description, '')"
        ")) STORED"
    )
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.execute(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {CONFIG}")
    # `unaccent` fica: outra coisa pode ter passado a depender dela, e extensão
    # ociosa não custa nada.
