import json
from pathlib import Path

from ingestion.models import AttributeSpec, NormalizedProduct
from ingestion.validate import read_categories, validate, validate_specs


def _schema():
    return [
        AttributeSpec(
            attribute_key="ram_gb", label="RAM", data_type="number", unit="GB", required=True
        ),
        AttributeSpec(attribute_key="anc", label="ANC", data_type="boolean", required=True),
        AttributeSpec(
            attribute_key="storage_type",
            label="Armazenamento",
            data_type="enum",
            allowed_values=["SSD", "HDD"],
            required=False,
        ),
    ]


def test_specs_validos_nao_tem_erro():
    assert validate_specs({"ram_gb": 16, "anc": True}, _schema()) == []


def test_required_faltando_gera_erro():
    erros = validate_specs({"anc": True}, _schema())
    assert any("ram_gb" in e for e in erros)


def test_tipo_errado_gera_erro():
    erros = validate_specs({"ram_gb": "16GB", "anc": True}, _schema())
    assert any("ram_gb" in e for e in erros)


def test_enum_fora_da_lista_gera_erro():
    erros = validate_specs({"ram_gb": 16, "anc": True, "storage_type": "SSHD"}, _schema())
    assert any("storage_type" in e for e in erros)


def _produto(category_slug: str, specs: dict) -> NormalizedProduct:
    return NormalizedProduct(
        slug="p",
        name="Produto",
        category_slug=category_slug,
        brand_slug="marca",
        brand_name="Marca",
        specs=specs,
    )


def test_validate_particiona_validos_e_rejeitados():
    schemas = {"notebooks": _schema()}
    produtos = [
        _produto("notebooks", {"ram_gb": 16, "anc": True}),
        _produto("notebooks", {"anc": True}),
        _produto("fones", {"ram_gb": 8, "anc": True}),
    ]
    validos, rejeitados = validate(produtos, schemas)
    assert len(validos) == 1
    assert len(rejeitados) == 2
    assert any("desconhecida" in r.reasons[0] for r in rejeitados)


def test_read_categories(tmp_path: Path):
    payload = [
        {
            "slug": "notebooks",
            "name": "Notebooks",
            "attributes": [
                {"attribute_key": "ram_gb", "label": "RAM", "data_type": "number", "required": True}
            ],
        }
    ]
    (tmp_path / "categories.json").write_text(json.dumps(payload), encoding="utf-8")
    categorias = read_categories(tmp_path)
    assert len(categorias) == 1
    assert categorias[0].slug == "notebooks"
    assert categorias[0].attributes[0].attribute_key == "ram_gb"


def test_read_categories_do_seed_real():
    seed_dir = Path(__file__).resolve().parent.parent / "seed"
    categorias = read_categories(seed_dir)
    slugs = {c.slug for c in categorias}
    assert {"notebooks", "headphones"} <= slugs
