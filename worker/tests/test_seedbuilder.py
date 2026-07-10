"""Testes do seed-builder: parser de título, mapeamento ML e cliente da API (mockado)."""

import io
import json

from tools.seedbuilder import ml_api
from tools.seedbuilder.build_seed import build
from tools.seedbuilder.mapping import map_attributes
from tools.seedbuilder.title_parser import extract_brand, parse_headphone, parse_notebook


def test_parse_notebook_extrai_specs():
    title = 'Notebook Lenovo IdeaPad Slim 3 Intel Core i5-13420H 8GB 512GB SSD 15.3"'
    specs = parse_notebook(title)
    assert specs["cpu"] == "Intel Core i5-13420H"
    assert specs["ram_gb"] == 8
    assert specs["storage_gb"] == 512
    assert specs["storage_type"] == "SSD"
    assert specs["screen_in"] == 15.3


def test_parse_notebook_tb_vira_gb():
    specs = parse_notebook("Notebook Acer Ryzen 7 7735HS 16gb 1tb SSD")
    assert specs["storage_gb"] == 1024
    assert specs["ram_gb"] == 16


def test_parse_notebook_core_ultra():
    specs = parse_notebook("Predator Helios Neo Intel Core Ultra 7 255HX 32GB 1TB SSD")
    assert specs["cpu"] == "Intel Core Ultra 7 255HX"
    assert specs["storage_gb"] == 1024
    assert specs["ram_gb"] == 32


def test_parse_notebook_tolera_marcas_registradas():
    specs = parse_notebook("Acer Nitro V Intel® Core™ i7-13620H 16GB 512SSD")
    assert specs["cpu"] == "Intel Core i7-13620H"
    assert specs["storage_gb"] == 512
    assert specs["storage_type"] == "SSD"
    assert specs["ram_gb"] == 16


def test_parse_notebook_nao_inventa_tela_de_codigo_de_modelo():
    # "A15"/"15irx9" são código de modelo, não a tela → screen_in deve ficar ausente.
    specs = parse_notebook("Notebook Gamer Asus TUF A15 Ryzen 7 7735HS 16GB 512GB SSD")
    assert "screen_in" not in specs


def test_extract_brand():
    assert extract_brand("notebooks", "Notebook Gamer Dell Alienware 16") == "Dell"
    assert extract_brand("notebooks", "Notebook Asus TUF Gaming") == "Asus"
    assert extract_brand("notebooks", "Notebook sem marca conhecida") is None


def test_extract_brand_por_sublinha():
    assert extract_brand("notebooks", "Notebook Gamer Predator Helios Neo PHN16") == "Acer"
    assert extract_brand("notebooks", "Notebook Rog Strix G16 Nvidia RTX 5070") == "Asus"


def test_map_attributes_notebook():
    attrs = [
        {"id": "PROCESSOR_MODEL", "name": "Modelo", "value_name": "Core i5-13420H"},
        {"id": "RAM_MEMORY", "name": "Memória RAM", "value_name": "8 GB"},
        {"id": "STORAGE_CAPACITY", "name": "Armazenamento", "value_name": "512 GB"},
        {"id": "HARD_DRIVE_TYPE", "name": "Tipo", "value_name": "SSD"},
        {"id": "DISPLAY_SIZE", "name": "Tela", "value_name": '15.6 "'},
    ]
    specs = map_attributes("notebooks", attrs)
    assert specs == {
        "cpu": "Core i5-13420H",
        "ram_gb": 8,
        "storage_gb": 512,
        "storage_type": "SSD",
        "screen_in": 15.6,
    }


def test_map_attributes_por_name_quando_id_desconhecido():
    attrs = [{"id": "X", "name": "RAM_MEMORY", "value_name": "16 GB"}]
    assert map_attributes("notebooks", attrs) == {"ram_gb": 16}


def test_parse_notebook_celeron():
    specs = parse_notebook("Notebook Lenovo Ideapad Intel Celeron N4020 4GB 128GB SSD")
    assert specs["cpu"] == "Intel Celeron N4020"
    assert specs["ram_gb"] == 4
    assert specs["storage_gb"] == 128


def test_parse_headphone_over_ear_com_bateria():
    specs = parse_headphone("Fone Dapon H02d Bluetooth 5.1 Over-ear 22 Horas De Bateria")
    assert specs["type"] == "over-ear"
    assert specs["anc"] is False
    assert specs["battery_h"] == 22
    assert specs["bluetooth"] == "5.1"


def test_parse_headphone_tws_anc():
    specs = parse_headphone("Fone TWS Bluetooth 5.3 Cancelamento de Ruído Ativo 35h com Microfone")
    assert specs["type"] == "earbuds"
    assert specs["anc"] is True
    assert specs["battery_h"] == 35
    assert specs["microphone"] is True


def test_parse_headphone_headset_vira_over_ear():
    assert parse_headphone("Headset Gamer Redragon Zeus")["type"] == "over-ear"


def test_extract_brand_headphones_e_sublinha():
    assert extract_brand("headphones", "Fone JBL Wave Beam 2") == "JBL"
    assert extract_brand("headphones", "Galaxy Buds Core Preto") == "Samsung"
    assert extract_brand("headphones", "soundcore P40i da Anker") == "Anker"


def test_build_filtra_dominio_e_acessorio():
    rows = [
        {
            "SKU": "MLB1",
            "eTituloProduto": "Fone JBL Tune TWS Bluetooth 5.3",
            "produtoDomainID": "MLB-HEADPHONES",
            "novoPreco": "199",
        },
        {
            "SKU": "MLB2",
            "eTituloProduto": "Suporte De Mesa Para Headset Gamer",
            "produtoDomainID": "MLB-HEADPHONES",
            "novoPreco": "50",
        },
        {
            "SKU": "MLB3",
            "eTituloProduto": "Controle Xbox Sem Fio",
            "produtoDomainID": "MLB-GAMEPADS_AND_JOYSTICKS",
            "novoPreco": "300",
        },
    ]
    products = build(rows, "headphones")
    assert [p["external_id"] for p in products] == ["MLB1"]


def _fake_urlopen(attributes):
    payload = json.dumps({"attributes": attributes}).encode("utf-8")

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _open(request, timeout=15):
        return _Resp(payload)

    return _open


def test_ml_api_fetch_attributes_parseia_resposta():
    attrs = [{"id": "RAM_MEMORY", "value_name": "8 GB"}]
    result = ml_api.fetch_attributes("MLB123", "tok", urlopen=_fake_urlopen(attrs))
    assert result == attrs


def test_ml_api_fetch_attributes_tolera_erro():
    def _boom(request, timeout=15):
        raise OSError("sem rede")

    assert ml_api.fetch_attributes("MLB123", "tok", urlopen=_boom) == []


def test_build_monta_rawproduct():
    rows = [
        {
            "SKU": "MLB1",
            "eTituloProduto": 'Notebook Dell Core i5-13420H 8GB 512GB SSD 15.6"',
            "produtoMarca": "",
            "novoPreco": "3999",
            "Vendedor": "Loja X",
            "Moeda": "BRL",
            "zProdutoLink": "https://exemplo/MLB1",
        }
    ]
    products = build(rows, "notebooks")
    assert len(products) == 1
    p = products[0]
    assert p["external_id"] == "MLB1"
    assert p["brand"] == "Dell"
    assert p["category"] == "notebooks"
    assert p["offers"][0]["price"] == "3999"
    assert p["specs"]["ram_gb"] == 8
