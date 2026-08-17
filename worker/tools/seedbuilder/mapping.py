"""Mapeia a ficha técnica do Mercado Livre → nossas ``attribute_key`` por categoria.

**Os IDs aqui são os de `/products/{id}` (catálogo)**, não os de `/items/{id}`
(anúncio). A versão anterior deste módulo procurava `RAM_MEMORY`,
`STORAGE_CAPACITY`, `HARD_DRIVE_TYPE` e `IS_TOUCHSCREEN` — nenhum existe no
payload de catálogo, que usa `RAM_MEMORY_MODULE_TOTAL_CAPACITY`,
`TOTAL_DISK_CAPACITY`, `DISK_TYPE` e `WITH_TOUCH_SCREEN`. Por isso o
enriquecimento nunca preencheu nada. Ver `ml_api.py` e o ADR-0009.

Todo valor abaixo foi **observado na API** (amostra de 2026-08-09), não deduzido:
`DISPLAY_SIZE` vem como `'15.6 "'`, `WEIGHT` como `'2.49 kg'`, os booleanos como
`'Sim'`/`'Não'` e `HEADPHONE_FORMAT` como `'In-ear'`/`'Clip-ear'`/`'Over-ear'`.

Cada chave lista IDs candidatos (em ordem de preferência) e um transformador. A
busca tenta por ``id`` e depois por ``name`` (case-insensitive).
"""

import re
from collections.abc import Callable

# --------------------------------------------------------------------------- #
# Transformadores                                                              #
# --------------------------------------------------------------------------- #


def _number(value: str | None) -> int | None:
    """``'8 GB'`` → 8 · ``'1 TB'`` → 1024 · ``'35 h'`` → 35."""
    if not value:
        return None
    match = re.search(r"([\d.,]+)\s*(gb|tb)?", value, re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1).replace(".", "").replace(",", ".")
    try:
        amount = float(digits)
    except ValueError:
        return None
    return int(amount * 1024) if (match.group(2) or "").lower() == "tb" else int(amount)


def _inches(value: str | None) -> float | None:
    """``'15.6 "'`` → 15.6. Fora da faixa de tela de notebook, descarta."""
    match = re.search(r"([\d.,]+)", value or "")
    if not match:
        return None
    try:
        polegadas = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    return polegadas if 10.0 <= polegadas <= 18.9 else None


def _kg(value: str | None) -> float | None:
    """``'2.49 kg'`` → 2.49 · ``'2490 g'`` → 2.49. Fora da faixa, descarta."""
    if not value:
        return None
    match = re.search(r"([\d.,]+)\s*(kg|g)?", value, re.IGNORECASE)
    if not match:
        return None
    try:
        quantidade = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    if (match.group(2) or "kg").lower() == "g":
        quantidade /= 1000
    # Notebook fora de 0,5–5 kg é erro de unidade no anúncio, não um notebook exótico.
    return round(quantidade, 2) if 0.5 <= quantidade <= 5.0 else None


def _storage_type(value: str | None) -> str | None:
    """Normaliza para o enum da categoria: ``SSD`` | ``HDD`` | ``eMMC``."""
    low = (value or "").lower()
    if "ssd" in low or "nvme" in low:
        return "SSD"
    if "emmc" in low:
        return "eMMC"
    return "HDD" if low else None


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _gpu(value: str | None) -> str | None:
    """Normaliza GPU dedicada: 'RTX 4050 6 GB GDDR6' → 'RTX 4050'."""
    if not value:
        return None

    match = re.search(
        r"\b(RTX|GTX|RX|Arc)\s*(\d{3,4})\s*(Ti|XT|SUPER)?\b",
        value,
        re.IGNORECASE,
    )

    if not match:
        return None

    family = match.group(1)
    model = match.group(2)
    suffix = match.group(3)

    if family.lower() == "arc":
        family = "Arc"
    else:
        family = family.upper()

    if suffix:
        suffix = suffix.upper() if suffix.lower() != "ti" else "Ti"
        return f"{family} {model} {suffix}"

    return f"{family} {model}"


def _boolean(value: str | None) -> bool:
    """A API responde ``'Sim'``/``'Não'`` (e às vezes ``'Yes'``)."""
    return (value or "").strip().lower() in {"sim", "yes", "true", "com"}


# Formatos que a API devolve → nosso enum (in-ear | on-ear | over-ear | earbuds).
# `Clip-ear`/`fone clip` descrevem a fixação, não a concha: o vizinho mais próximo
# no enum é `earbuds` (mesma decisão do `title_parser`). Valores fora da tabela —
# a API às vezes devolve `'6.0'` neste campo — são descartados, não chutados.
_FORMATO_FONE = {
    "in-ear": "in-ear",
    "in ear": "in-ear",
    "intra-auricular": "in-ear",
    "on-ear": "on-ear",
    "on ear": "on-ear",
    "supra-auricular": "on-ear",
    "over-ear": "over-ear",
    "over ear": "over-ear",
    "circum-auricular": "over-ear",
    "headphone": "over-ear",
    "headset": "over-ear",
    "earbud": "earbuds",
    "earbuds": "earbuds",
    "clip-ear": "earbuds",
    "clip ear": "earbuds",
    "ear-clip": "earbuds",
    "fone clip": "earbuds",
    "open-ear": "earbuds",
    "open ear": "earbuds",
    "true wireless": "earbuds",
}


def _headphone_format(value: str | None) -> str | None:
    return _FORMATO_FONE.get((value or "").strip().lower())


_Transform = Callable[[str | None], object]

# --------------------------------------------------------------------------- #
# Mapas por categoria                                                          #
# --------------------------------------------------------------------------- #

NOTEBOOK: dict[str, tuple[list[str], _Transform]] = {
    "ram_gb": (
        ["RAM_MEMORY_MODULE_TOTAL_CAPACITY", "RAM_MEMORY", "MEMORY_RAM", "RAM"],
        _number,
    ),
    "gpu": (
        ["DEDICATED_GRAPHIC_CARD_MODEL", "DEDICATED_GRAPHIC_CARD_LINE"],
        _gpu,
    ),
    "storage_gb": (
        [
            "TOTAL_DISK_CAPACITY",
            "SSD_DATA_STORAGE_CAPACITY",
            "STORAGE_CAPACITY",
            "HARD_DRIVE_CAPACITY",
        ],
        _number,
    ),
    "storage_type": (["DISK_TYPE", "HARD_DRIVE_TYPE", "STORAGE_TYPE"], _storage_type),
    "screen_in": (["DISPLAY_SIZE", "SCREEN_SIZE"], _inches),
    "weight_kg": (["WEIGHT", "PRODUCT_WEIGHT"], _kg),
    "touchscreen": (["WITH_TOUCH_SCREEN", "IS_TOUCHSCREEN", "WITH_TOUCHSCREEN"], _boolean),
    # `cpu` não sai de um atributo só — ver `_compoe_cpu`.
}

HEADPHONE: dict[str, tuple[list[str], _Transform]] = {
    "type": (["HEADPHONE_FORMAT", "FORMAT"], _headphone_format),
    "anc": (
        ["WITH_NOISE_CANCELLING", "WITH_ACTIVE_NOISE_CANCELLATION", "IS_NOISE_CANCELLING"],
        _boolean,
    ),
    "battery_h": (["HEADPHONE_MAX_BATTERY_LIFE", "BATTERY_DURATION"], _number),
    "bluetooth": (["BLUETOOTH_VERSION"], _text),
    "microphone": (["WITH_MICROPHONE", "HAS_MICROPHONE"], _boolean),
    "water_resistant": (["IS_WATER_RESISTANT", "IS_WATERPROOF"], _boolean),
}

MAPS: dict[str, dict[str, tuple[list[str], _Transform]]] = {
    "notebooks": NOTEBOOK,
    "headphones": HEADPHONE,
}

# `battery_wh` fica de fora de propósito: a API expõe `BATTERY_CAPACITY` em Ah/mAh
# ('3.574 Ah', '41 mAh'), não em Wh. Converter exigiria a tensão da bateria, que
# não vem — e um número em unidade errada é pior que a ausência. Ver ADR-0009.


def _compoe_cpu(by_id: dict[str, str]) -> str | None:
    """Monta o `cpu` a partir dos três atributos que o ML usa.

    A API fragmenta o processador: `PROCESSOR_BRAND` ('Intel'), `PROCESSOR_LINE`
    ('Core i5' ou 'INTEL CORE I5') e `PROCESSOR_MODEL` (ora '13420H', ora
    'Intel Core i5-13420H'). Nenhum sozinho serve. Concatenamos evitando repetir
    o que já está contido — senão sai "Intel Intel Core i5 Intel Core i5-13420H".
    """
    partes: list[str] = []
    for chave in ("PROCESSOR_BRAND", "PROCESSOR_LINE", "PROCESSOR_MODEL"):
        valor = (by_id.get(chave) or "").strip()
        if not valor:
            continue
        acumulado = " ".join(partes).lower()
        if valor.lower() in acumulado:
            continue
        # O model já costuma trazer marca e linha; nesse caso ele substitui tudo.
        if partes and all(p.lower() in valor.lower() for p in partes):
            partes = [valor]
            continue
        partes.append(valor)

    return " ".join(partes).strip() or None


def map_attributes(category: str, ml_attributes: list[dict]) -> dict:
    """Converte a ficha técnica do ML nos specs do nosso schema."""
    by_id = {(a.get("id") or "").upper(): a.get("value_name") for a in ml_attributes}
    by_name = {(a.get("name") or "").upper(): a.get("value_name") for a in ml_attributes}

    specs: dict = {}
    for key, (candidates, transform) in MAPS.get(category, {}).items():
        raw = next((by_id[c] for c in candidates if by_id.get(c)), None)
        if raw is None:
            raw = next((by_name[c] for c in candidates if by_name.get(c)), None)
        if raw is not None:
            value = transform(raw)
            if value is not None:
                specs[key] = value

    if category == "notebooks":
        cpu = _compoe_cpu(by_id)
        if cpu:
            specs["cpu"] = cpu

    # Sem formato declarado, TWS resolve: é a tecnologia dos earbuds sem fio.
    if (
        category == "headphones"
        and "type" not in specs
        and _boolean(by_id.get("WITH_TWS_TECHNOLOGY"))
    ):
        specs["type"] = "earbuds"

    return specs
