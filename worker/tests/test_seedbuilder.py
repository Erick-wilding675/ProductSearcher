"""Testes do seed-builder: parser de título, mapeamento ML e cliente da API (mockado)."""

import io
import json
import urllib.error

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
    # IDs e valores exatamente como /products/{id} devolve (amostrado em 2026-08-09).
    attrs = [
        {"id": "PROCESSOR_BRAND", "name": "Marca do processador", "value_name": "Intel"},
        {"id": "PROCESSOR_LINE", "name": "Linha", "value_name": "Core i5"},
        {"id": "PROCESSOR_MODEL", "name": "Modelo", "value_name": "13420H"},
        {"id": "RAM_MEMORY_MODULE_TOTAL_CAPACITY", "name": "RAM", "value_name": "8 GB"},
        {"id": "TOTAL_DISK_CAPACITY", "name": "Armazenamento", "value_name": "512 GB"},
        {"id": "DISK_TYPE", "name": "Tipo", "value_name": "SSD"},
        {"id": "DISPLAY_SIZE", "name": "Tela", "value_name": '15.6 "'},
        {"id": "WEIGHT", "name": "Peso", "value_name": "2.38 kg"},
        {"id": "WITH_TOUCH_SCREEN", "name": "Touch", "value_name": "Não"},
    ]
    specs = map_attributes("notebooks", attrs)
    assert specs == {
        "cpu": "Intel Core i5 13420H",
        "ram_gb": 8,
        "storage_gb": 512,
        "storage_type": "SSD",
        "screen_in": 15.6,
        "weight_kg": 2.38,
        "touchscreen": False,
    }


def test_map_attributes_notebook_tb_e_cpu_completo_no_model():
    # Quando PROCESSOR_MODEL já traz marca e linha, não repetimos os três.
    attrs = [
        {"id": "PROCESSOR_BRAND", "value_name": "Intel"},
        {"id": "PROCESSOR_LINE", "value_name": "Core i5"},
        {"id": "PROCESSOR_MODEL", "value_name": "Intel Core i5-13420H"},
        {"id": "TOTAL_DISK_CAPACITY", "value_name": "1 TB"},
    ]
    specs = map_attributes("notebooks", attrs)
    assert specs["cpu"] == "Intel Core i5-13420H"
    assert specs["storage_gb"] == 1024


def test_map_attributes_headphone():
    attrs = [
        {"id": "HEADPHONE_FORMAT", "value_name": "In-ear"},
        {"id": "WITH_NOISE_CANCELLING", "value_name": "Sim"},
        {"id": "HEADPHONE_MAX_BATTERY_LIFE", "value_name": "35 h"},
        {"id": "BLUETOOTH_VERSION", "value_name": "5.3"},
        {"id": "WITH_MICROPHONE", "value_name": "Sim"},
        {"id": "IS_WATER_RESISTANT", "value_name": "Não"},
    ]
    assert map_attributes("headphones", attrs) == {
        "type": "in-ear",
        "anc": True,
        "battery_h": 35,
        "bluetooth": "5.3",
        "microphone": True,
        "water_resistant": False,
    }


def test_map_attributes_formato_clip_vira_earbuds():
    attrs = [{"id": "HEADPHONE_FORMAT", "value_name": "Clip-ear"}]
    assert map_attributes("headphones", attrs)["type"] == "earbuds"


def test_map_attributes_formato_invalido_nao_vira_spec():
    # A API às vezes devolve lixo neste campo ('6.0'). Descartar > chutar.
    attrs = [{"id": "HEADPHONE_FORMAT", "value_name": "6.0"}]
    assert "type" not in map_attributes("headphones", attrs)


def test_map_attributes_tws_supre_formato_ausente():
    attrs = [{"id": "WITH_TWS_TECHNOLOGY", "value_name": "Sim"}]
    assert map_attributes("headphones", attrs)["type"] == "earbuds"


def test_map_attributes_peso_absurdo_e_descartado():
    # '2380 kg' é erro de unidade no anúncio, não um notebook de duas toneladas.
    attrs = [{"id": "WEIGHT", "value_name": "2380 kg"}]
    assert "weight_kg" not in map_attributes("notebooks", attrs)


def test_map_attributes_por_name_quando_id_desconhecido():
    attrs = [{"id": "X", "name": "RAM_MEMORY_MODULE_TOTAL_CAPACITY", "value_name": "16 GB"}]
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


# --- marcas menores do marketplace ------------------------------------------
# "marca ausente" era o maior motivo de rejeição da ingestão (60 de 112), bem
# acima de specs faltando. Todas estas saem literalmente do título do anúncio.


def test_extract_brand_marcas_menores():
    assert extract_brand("headphones", "Headphone Dapon H02D Pro ANC Over Ear") == "Dapon"
    assert extract_brand("headphones", "Headset Gamer Sem Fio OLAFVI CT790 Wireless") == "Olafvi"
    assert extract_brand("headphones", "Fone de Ouvido JSKJ Esportivo OWS TWS") == "JSKJ"
    assert extract_brand("headphones", "Fone De Ouvido In-ear Bluetooth Htc Ne76") == "HTC"
    assert extract_brand("headphones", "Fone de Ouvido Davely A520 In-Ear") == "Davely"


def test_extract_brand_ainda_devolve_none_para_generico():
    # Anúncio sem marca alguma continua sendo rejeitado — o parser não inventa.
    assert extract_brand("headphones", "Fone De Ouvido Bluetooth 5.0 A Prova De Suor Preto") is None


# --- formato do fone ---------------------------------------------------------


def test_parse_headphone_clipe_e_ouvido_aberto_viram_earbuds():
    # Clipe/gancho/condução não casam com in/on/over-ear; `earbuds` é o vizinho
    # mais próximo dentro do enum da categoria.
    assert parse_headphone("Fone Basike Sem Fio Ear-Clip Ba-FON349")["type"] == "earbuds"
    assert parse_headphone("Fone Monster Open Ear AC601 Clip-ear")["type"] == "earbuds"
    assert parse_headphone("Fone Philips Ear Cuff Sem Fio Bluetooth")["type"] == "earbuds"
    assert parse_headphone("Fone Lumva Bluetooth Condução Aérea")["type"] == "earbuds"


def test_parse_headphone_sem_fio_sem_marcador_vira_earbuds():
    # Último recurso: sem NENHUM marcador de formato, "fone sem fio/bluetooth"
    # é TWS em praticamente todo o catálogo.
    assert parse_headphone("Fone De Ouvido Sem Fio Havit Tw982 Bluetooth 5.4")["type"] == "earbuds"
    assert parse_headphone("Fone De Ouvido Bluetooth Lenovo Le208 Sem Fio")["type"] == "earbuds"


def test_parse_headphone_marcador_explicito_ganha_do_fallback():
    # O fallback é o último ramo: qualquer marcador explícito tem precedência.
    assert parse_headphone("Headphone Sem Fio Bluetooth 5.3 Over Ear")["type"] == "over-ear"
    assert parse_headphone("Fone Bluetooth Sem Fio In-ear Duplo")["type"] == "in-ear"
    assert parse_headphone("Headset Gamer Sem Fio Bluetooth")["type"] == "over-ear"


def test_parse_headphone_com_fio_sem_marcador_nao_chuta_formato():
    assert "type" not in parse_headphone("Fone De Ouvido Branco 3,5mm H2015se-white")


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


def _fake_urlopen(payload_por_path):
    """urlopen falso: casa pelo trecho do path e devolve o JSON correspondente."""

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _open(request, timeout=15):
        for trecho, payload in payload_por_path.items():
            if trecho in request.full_url:
                return _Resp(json.dumps(payload).encode("utf-8"))
        raise urllib.error.HTTPError(request.full_url, 404, "not found", None, None)

    return _open


def test_ml_client_product_usa_endpoint_de_catalogo():
    # Os external_id do seed são ids de CATÁLOGO: /items dá 404, /products responde.
    ficha = {"name": "Notebook X", "attributes": [{"id": "MODEL", "value_name": "LOQ 15"}]}
    client = ml_api.MLClient("tok", urlopen=_fake_urlopen({"/products/MLB123": ficha}))

    resultado = client.product("MLB123")

    assert resultado == ficha


def test_ml_client_devolve_none_em_404():
    # Produto despublicado desde a coleta é rotina, não erro.
    client = ml_api.MLClient("tok", urlopen=_fake_urlopen({}))
    assert client.product("MLB123") is None


def test_ml_client_tolera_falha_de_rede():
    def _boom(request, timeout=15):
        raise OSError("sem rede")

    client = ml_api.MLClient("tok", urlopen=_boom)
    assert client.product("MLB123") is None
    assert client.product_items("MLB123") == []
    assert client.user(1) is None


def test_ml_client_product_items_lista_ofertas():
    payload = {"results": [{"item_id": "MLB9", "price": 5877, "seller_id": 1}]}
    client = ml_api.MLClient("tok", urlopen=_fake_urlopen({"/products/MLB123/items": payload}))

    assert client.product_items("MLB123") == payload["results"]


def test_product_fields_extrai_model_e_description():
    ficha = {
        "name": "Notebook Gamer Lenovo LOQ 15IRX9",
        "short_description": {"content": "Eleve seu desempenho."},
        "attributes": [{"id": "MODEL", "value_name": "LOQ 15IRX9"}],
    }

    campos = ml_api.product_fields(ficha)

    assert campos["model"] == "LOQ 15IRX9"
    assert campos["description"] == "Eleve seu desempenho."
    assert campos["catalog_name"] == "Notebook Gamer Lenovo LOQ 15IRX9"


def test_product_fields_extrai_identidade_do_catalogo():
    ficha = {
        "parent_id": "MLB45574030",
        "attributes": [{"id": "ALPHANUMERIC_MODEL", "value_name": "83KH0001BR"}],
    }

    campos = ml_api.product_fields(ficha)

    assert campos["catalog_parent_id"] == "MLB45574030"
    assert campos["catalog_sku"] == "83KH0001BR"


def test_product_fields_tolera_ficha_incompleta():
    assert ml_api.product_fields({}) == {
        "catalog_name": None,
        "model": None,
        "description": None,
        "catalog_parent_id": None,
        "catalog_sku": None,
    }


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
