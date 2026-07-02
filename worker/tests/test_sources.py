import textwrap
from pathlib import Path

from ingestion.models import RawProduct
from ingestion.sources import IngestionSource, SeedIngestionSource


def _write(dir_: Path, name: str, content: str) -> None:
    """Escreve um arquivo YAML no diretório, removendo a indentação do bloco."""
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(textwrap.dedent(content), encoding="utf-8")


def test_seed_source_le_yaml_cru(tmp_path: Path):
    _write(
        tmp_path / "products",
        "notebooks.yaml",
        """
        - source: seed
          name: Notebook X
          category: notebooks
          brand: Acme
          specs: {ram_gb: 16}
          offers:
            - {store: Loja A, price: "R$ 3.999,00"}
        """,
    )

    source = SeedIngestionSource(tmp_path)
    result = list(source.fetch())

    assert isinstance(source, IngestionSource)  # cumpre o contrato
    assert len(result) == 1
    assert isinstance(result[0], RawProduct)
    assert result[0].offers[0].price == "R$ 3.999,00"  # segue cru


def test_diretorio_de_produtos_ausente_devolve_vazio(tmp_path: Path):
    # tmp_path existe, mas não tem a subpasta products/
    source = SeedIngestionSource(tmp_path)
    assert list(source.fetch()) == []


def test_le_multiplos_arquivos_em_ordem(tmp_path: Path):
    products = tmp_path / "products"
    _write(products, "a_fones.yaml", "- {source: seed, name: Fone A, category: headphones}\n")
    _write(
        products,
        "b_notebooks.yaml",
        "- {source: seed, name: Notebook B, category: notebooks}\n",
    )

    nomes = [p.name for p in SeedIngestionSource(tmp_path).fetch()]

    assert nomes == ["Fone A", "Notebook B"]  # ordenado por nome de arquivo


def test_registro_malformado_e_pulado(tmp_path: Path):
    # o segundo registro não tem os campos obrigatórios (name/category)
    _write(
        tmp_path / "products",
        "notebooks.yaml",
        """
        - {source: seed, name: Notebook Bom, category: notebooks}
        - {source: seed}
        """,
    )

    result = list(SeedIngestionSource(tmp_path).fetch())

    assert len(result) == 1
    assert result[0].name == "Notebook Bom"
