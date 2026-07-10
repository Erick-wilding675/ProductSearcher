"""Mapeia atributos da API do Mercado Livre → nossas ``attribute_key`` por categoria.

Cada chave lista IDs de atributo candidatos (o ML varia os nomes) e um transformador
de valor. A busca tenta por ``id`` e depois por ``name`` (case-insensitive).
"""

import re
from collections.abc import Callable


def _number(value: str | None) -> int | None:
    """'8 GB' → 8 ; '1 TB' → 1024 ; '512 GB' → 512."""
    if not value:
        return None
    match = re.search(r"([\d.,]+)\s*(gb|tb)?", value, re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1).replace(".", "").replace(",", ".")
    amount = float(digits)
    return int(amount * 1024) if (match.group(2) or "").lower() == "tb" else int(amount)


def _inches(value: str | None) -> float | None:
    match = re.search(r"([\d.,]+)", value or "")
    return float(match.group(1).replace(",", ".")) if match else None


def _storage_type(value: str | None) -> str | None:
    low = (value or "").lower()
    if "ssd" in low or "nvme" in low:
        return "SSD"
    if "emmc" in low:
        return "eMMC"
    return "HDD" if low else None


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _boolean(value: str | None) -> bool:
    return (value or "").strip().lower() in {"sim", "yes", "true", "com"}


_Transform = Callable[[str | None], object]

NOTEBOOK: dict[str, tuple[list[str], _Transform]] = {
    "cpu": (["PROCESSOR_MODEL", "PROCESSOR_LINE", "LINE_PROCESSOR", "PROCESSOR"], _text),
    "ram_gb": (["RAM_MEMORY", "MEMORY_RAM", "RAM"], _number),
    "storage_gb": (
        ["STORAGE_CAPACITY", "HARD_DRIVE_CAPACITY", "SSD_CAPACITY", "TOTAL_STORAGE_CAPACITY"],
        _number,
    ),
    "storage_type": (["HARD_DRIVE_TYPE", "STORAGE_TYPE", "TYPE_OF_STORAGE"], _storage_type),
    "screen_in": (["DISPLAY_SIZE", "SCREEN_SIZE", "SIZE_SCREEN"], _inches),
    "touchscreen": (["IS_TOUCHSCREEN", "WITH_TOUCHSCREEN"], _boolean),
}

HEADPHONE: dict[str, tuple[list[str], _Transform]] = {
    "type": (["HEADPHONE_FORMAT", "FORMAT", "TYPE"], _text),
    "anc": (["WITH_ACTIVE_NOISE_CANCELLATION", "IS_NOISE_CANCELLING"], _boolean),
    "battery_h": (["BATTERY_DURATION", "BATTERY_LIFE"], _number),
    "bluetooth": (["BLUETOOTH_VERSION"], _text),
}

MAPS: dict[str, dict[str, tuple[list[str], _Transform]]] = {
    "notebooks": NOTEBOOK,
    "headphones": HEADPHONE,
}


def map_attributes(category: str, ml_attributes: list[dict]) -> dict:
    """Converte a lista de atributos do ML nos specs do nosso schema."""
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
    return specs
