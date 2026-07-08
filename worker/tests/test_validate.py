from ingestion.models import AttributeSpec
from ingestion.validate import validate_specs


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
    erros = validate_specs({"anc": True}, _schema())  # sem ram_gb
    assert any("ram_gb" in e for e in erros)


def test_tipo_errado_gera_erro():
    erros = validate_specs({"ram_gb": "16GB", "anc": True}, _schema())  # string, não número
    assert any("ram_gb" in e for e in erros)


def test_enum_fora_da_lista_gera_erro():
    erros = validate_specs({"ram_gb": 16, "anc": True, "storage_type": "SSHD"}, _schema())
    assert any("storage_type" in e for e in erros)
