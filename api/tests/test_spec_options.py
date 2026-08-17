"""Testes das opções de especificação disponíveis para priorização."""

from app.search.intent import RuleBasedIntentParser
from app.search.ranking import DeterministicRanking
from app.search.service import SearchService


class _FakeProvider:
    def __init__(self, hits: list[dict]) -> None:
        self._hits = hits

    def search(self, intent, filters=None, page=1):
        return self._hits


class _FakeCatalog:
    def __init__(self, labels: dict[str, str]) -> None:
        self._labels = labels

    def get_attribute_labels(self, category: str) -> dict[str, str]:
        return self._labels


def _service(
    hits: list[dict],
    labels: dict[str, str],
) -> SearchService:
    return SearchService(
        RuleBasedIntentParser(),
        _FakeProvider(hits),
        DeterministicRanking(),
        catalog=_FakeCatalog(labels),
    )


def test_spec_options_retorna_valores_e_contagens():
    service = _service(
        hits=[
            {
                "attributes": {
                    "gpu": "RTX 4050",
                    "ram_gb": 16,
                }
            },
            {
                "attributes": {
                    "gpu": "RTX 4050",
                    "ram_gb": 8,
                }
            },
            {
                "attributes": {
                    "gpu": "RTX 3050",
                    "ram_gb": 16,
                }
            },
        ],
        labels={
            "gpu": "Placa de vídeo",
            "ram_gb": "Memória (GB)",
        },
    )

    response = service.spec_options(
        category="notebooks",
    )

    specs = {spec.key: spec for spec in response.specs}

    assert set(specs) == {
        "gpu",
        "ram_gb",
    }

    gpu_values = {value.value: value.count for value in specs["gpu"].values}

    assert gpu_values == {
        "RTX 4050": 2,
        "RTX 3050": 1,
    }

    ram_values = {value.value: value.count for value in specs["ram_gb"].values}

    assert ram_values == {
        16: 2,
        8: 1,
    }


def test_spec_options_ignora_specs_fora_do_schema_da_categoria():
    service = _service(
        hits=[
            {
                "attributes": {
                    "gpu": "RTX 4050",
                    "campo_desconhecido": "x",
                }
            }
        ],
        labels={
            "gpu": "Placa de vídeo",
        },
    )

    response = service.spec_options(
        category="notebooks",
    )

    assert [spec.key for spec in response.specs] == ["gpu"]


def test_spec_options_ignora_valores_complexos():
    service = _service(
        hits=[
            {
                "attributes": {
                    "gpu": "RTX 4050",
                    "extra": ["a", "b"],
                }
            }
        ],
        labels={
            "gpu": "Placa de vídeo",
            "extra": "Extra",
        },
    )

    response = service.spec_options(
        category="notebooks",
    )

    assert [spec.key for spec in response.specs] == ["gpu"]


def test_spec_options_remove_spec_de_alta_cardinalidade():
    hits = [
        {
            "attributes": {
                "cpu": f"CPU {i}",
                "gpu": ("RTX 4050" if i % 2 == 0 else "RTX 3050"),
            }
        }
        for i in range(21)
    ]

    service = _service(
        hits=hits,
        labels={
            "cpu": "Processador",
            "gpu": "Placa de vídeo",
        },
    )

    response = service.spec_options(
        category="notebooks",
    )

    keys = {spec.key for spec in response.specs}

    # 21 valores distintos ultrapassam MAX_SPEC_OPTION_VALUES = 20.
    assert "cpu" not in keys

    # GPU continua disponível porque tem baixa cardinalidade.
    assert "gpu" in keys


def test_spec_options_mantem_exatamente_vinte_valores():
    hits = [
        {
            "attributes": {
                "spec": f"valor-{i}",
            }
        }
        for i in range(20)
    ]

    service = _service(
        hits=hits,
        labels={
            "spec": "Spec de teste",
        },
    )

    response = service.spec_options(
        category="notebooks",
    )

    assert len(response.specs) == 1
    assert response.specs[0].key == "spec"
    assert len(response.specs[0].values) == 20


def test_spec_options_sem_categoria_retorna_lista_vazia():
    service = _service(
        hits=[
            {
                "attributes": {
                    "gpu": "RTX 4050",
                }
            }
        ],
        labels={
            "gpu": "Placa de vídeo",
        },
    )

    response = service.spec_options()

    assert response.specs == []


def test_spec_options_sem_catalogo_retorna_lista_vazia():
    service = SearchService(
        RuleBasedIntentParser(),
        _FakeProvider(
            [
                {
                    "attributes": {
                        "gpu": "RTX 4050",
                    }
                }
            ]
        ),
        DeterministicRanking(),
    )

    response = service.spec_options(
        category="notebooks",
    )

    assert response.specs == []
