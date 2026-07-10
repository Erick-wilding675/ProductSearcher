"""Extrai specs a partir do título do anúncio (fallback quando a API não cobre).

Determinístico e testável. Tolera ``™``/``®`` e cobre CPU (incl. Core Ultra, formas
curtas ``I5-13420h``/``Ci5``/``R7`` e famílias sem número), RAM, armazenamento e
marca/sub-marca. A tela (``screen_in``) só sai de marcadores explícitos — números
soltos costumam ser código de modelo (``A15``, ``15irx9``), não a tela.
"""

import re
import unicodedata

BRANDS: dict[str, list[str]] = {
    "notebooks": [
        "Alienware",
        "Lenovo",
        "Asus",
        "Acer",
        "Dell",
        "Samsung",
        "HP",
        "Positivo",
        "Apple",
        "Vaio",
        "Gigabyte",
        "MSI",
        "Avell",
        "LG",
        "Nimo",
    ],
    "headphones": [
        "JBL",
        "Sony",
        "Samsung",
        "Apple",
        "Xiaomi",
        "Redmi",
        "Edifier",
        "Motorola",
        "Philips",
        "Bose",
        "LG",
        "QCY",
        "Baseus",
        "Havit",
        "Anker",
        "Monster",
        "Pulse",
        "Multilaser",
        "ELG",
        "Fortrek",
        "Warrior",
        "Redragon",
        "Onikuma",
        "Logitech",
        "HyperX",
        "Razer",
        "Jabra",
        "Plantronics",
        "Poly",
        "Lenovo",
        "HP",
        "Aiwa",
        "OneOdio",
        "Cowin",
        "Samzhe",
        "Kaidi",
        "Inova",
        "Basike",
        "Fallen",
        "Dex",
        "Knup",
        "Intelbras",
        "Sennheiser",
        "AKG",
        "Beats",
        "Marshall",
        "Skullcandy",
        "JLab",
        "Realme",
        "Miniso",
        "Positivo",
        "Bright",
        "Dazz",
    ],
}

# Sub-marca/linha → marca (quando o fabricante não aparece explícito no título).
_SUBBRANDS: dict[str, str] = {
    "predator": "Acer",
    "nitro": "Acer",
    "aspire": "Acer",
    "rog": "Asus",
    "zenbook": "Asus",
    "vivobook": "Asus",
    "tuf": "Asus",
    "ideapad": "Lenovo",
    "legion": "Lenovo",
    "thinkbook": "Lenovo",
    "thinkpad": "Lenovo",
    "yoga": "Lenovo",
    "loq": "Lenovo",
    "inspiron": "Dell",
    "latitude": "Dell",
    "vostro": "Dell",
    "alienware": "Dell",
    "pavilion": "HP",
    "omen": "HP",
    "victus": "HP",
}

# Sub-marca/linha → marca, específico de fones.
_SUBBRANDS_HP: dict[str, str] = {"soundcore": "Anker", "galaxy": "Samsung", "erazer": "Lenovo"}

_RAM_SIZES = {4, 6, 8, 12, 16, 24, 32, 48, 64}

# CPU (ordem de precedência). Busca em título já sem ™/®.
_CPU_ULTRA = re.compile(r"core\s+ultra\s+([3-9])\s*-?\s*([0-9]{3}[a-z]{0,2})?", re.I)
_CPU_IX = re.compile(r"core\s+i\s*-?\s*([3-9])\s*-?\s*([0-9]{3,5}[a-z]{0,3})", re.I)
_CPU_RYZEN = re.compile(r"ryzen\s+([3-9])\s+([0-9]{3,5}[a-z]{0,2})", re.I)
_CPU_CORE_N = re.compile(r"core\s+([3-9])\s+([0-9]{2,4}[a-z]{0,3})", re.I)
_CPU_IX_BARE = re.compile(r"\bi\s*-?\s*([3-9])\s*-?\s*([0-9]{3,5}[a-z]{0,3})?\b", re.I)
_CPU_CI = re.compile(r"\bc\s*i\s*([3-9])\s*-?\s*([0-9]{3,5}[a-z]{0,3})?", re.I)
_CPU_R_SHORT = re.compile(r"\br([3-9])\b", re.I)
_CPU_CLASSIC = re.compile(r"\b(celeron|pentium|athlon)\b(?:\s+([a-z]?\d{3,4}[a-z]?))?", re.I)
_CPU_FAMILY = re.compile(
    r"core\s+ultra\s+([3-9])|core\s+i([3-9])|ryzen\s+([3-9])|core\s*([3-9])", re.I
)

_STORAGE_FULL = re.compile(r"(\d+)\s*(gb|tb)\s*(?:de\s+)?(ssd|hd|hdd|emmc|nvme)", re.I)
_STORAGE_GLUED = re.compile(r"(\d{3,4})\s*(ssd|hdd|nvme|emmc)", re.I)
_STORAGE_TYPE_FIRST = re.compile(r"(ssd|hd|hdd|emmc|nvme)\s*(?:de\s*)?(\d+)\s*(gb|tb)", re.I)
_STORAGE_TB = re.compile(r"(\d+)\s*tb", re.I)
_TYPE_TOKEN = re.compile(r"\b(ssd|nvme|emmc|hdd|hd)\b", re.I)

_RAM = re.compile(r"(\d+)\s*gb\s*(?:de\s*)?ram|ram\s*(?:de\s*)?(\d+)\s*gb", re.I)
_GB = re.compile(r"(\d+)\s*(gb|tb)", re.I)

# Fones: bateria (h) e versão de Bluetooth.
_HP_BATTERY = re.compile(r"(\d{1,3})\s*h(?:oras)?\b", re.I)
_HP_BLUETOOTH = re.compile(r"bluetooth\s*(\d(?:\.\d)?)", re.I)

# Tela: só marcadores confiáveis (unidade explícita, "tela N" ou decimal N,N).
_SCREEN_UNIT = re.compile(r"(\d{2}(?:[.,]\d)?)\s*(?:\"|''|”|″|polegadas|pol\b)", re.I)
_SCREEN_TELA = re.compile(r"tela\s*(?:de\s*)?(\d{2}(?:[.,]\d)?)", re.I)
_SCREEN_DECIMAL = re.compile(r"\b(1[0-8][.,]\d)\b")


def _clean(text: str) -> str:
    return text.replace("™", " ").replace("®", " ").replace("©", " ")


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _to_gb(number: str, unit: str) -> int:
    return int(number) * (1024 if unit.lower() == "tb" else 1)


def _storage_type_from(token: str) -> str:
    return {"ssd": "SSD", "nvme": "SSD", "emmc": "eMMC"}.get(token.lower(), "HDD")


def extract_brand(category: str, title: str) -> str | None:
    """Marca conhecida no título; senão, deduz pela sub-marca/linha."""
    low = _ascii(title)
    for brand in BRANDS.get(category, []):
        if re.search(rf"\b{re.escape(_ascii(brand))}\b", low):
            return "Dell" if brand == "Alienware" else brand
    subs = _SUBBRANDS if category == "notebooks" else _SUBBRANDS_HP
    for sub, brand in subs.items():
        if re.search(rf"\b{sub}\b", low):
            return brand
    return None


def _parse_cpu(title: str) -> str | None:
    if m := _CPU_ULTRA.search(title):
        return f"Intel Core Ultra {m.group(1)}" + (f" {m.group(2).upper()}" if m.group(2) else "")
    if m := _CPU_IX.search(title):
        return f"Intel Core i{m.group(1)}-{m.group(2).upper()}"
    if m := _CPU_RYZEN.search(title):
        return f"AMD Ryzen {m.group(1)} {m.group(2).upper()}"
    if m := _CPU_CORE_N.search(title):
        return f"Intel Core {m.group(1)} {m.group(2).upper()}"
    if m := _CPU_IX_BARE.search(title):
        return f"Intel Core i{m.group(1)}" + (f"-{m.group(2).upper()}" if m.group(2) else "")
    if m := _CPU_CI.search(title):
        return f"Intel Core i{m.group(1)}" + (f"-{m.group(2).upper()}" if m.group(2) else "")
    if m := _CPU_R_SHORT.search(title):
        return f"AMD Ryzen {m.group(1)}"
    if m := _CPU_CLASSIC.search(title):
        nome = m.group(1).capitalize()
        return f"Intel {nome} {m.group(2).upper()}" if m.group(2) else f"Intel {nome}"
    if m := _CPU_FAMILY.search(title):
        if m.group(1):
            return f"Intel Core Ultra {m.group(1)}"
        if m.group(2):
            return f"Intel Core i{m.group(2)}"
        if m.group(3):
            return f"AMD Ryzen {m.group(3)}"
        return f"Intel Core {m.group(4)}"
    return None


def _parse_storage(title: str) -> tuple[int | None, str | None]:
    if m := _STORAGE_FULL.search(title):
        return _to_gb(m.group(1), m.group(2)), _storage_type_from(m.group(3))
    if m := _STORAGE_GLUED.search(title):
        return int(m.group(1)), _storage_type_from(m.group(2))
    if m := _STORAGE_TYPE_FIRST.search(title):
        gb = _to_gb(m.group(2), m.group(3))
        if gb >= 128:
            return gb, _storage_type_from(m.group(1))
    if m := _STORAGE_TB.search(title):
        tok = _TYPE_TOKEN.search(title)
        return int(m.group(1)) * 1024, (_storage_type_from(tok.group(1)) if tok else "SSD")
    for num, unit in _GB.findall(title):
        gb = _to_gb(num, unit)
        if unit.lower() == "gb" and gb >= 128:
            return gb, "SSD"
    return None, None


def _parse_screen(title: str) -> float | None:
    for rx in (_SCREEN_UNIT, _SCREEN_TELA, _SCREEN_DECIMAL):
        if m := rx.search(title):
            val = float(m.group(1).replace(",", "."))
            if 10.0 <= val <= 18.9:
                return val
    return None


def parse_notebook(title: str) -> dict:
    title = _clean(title)
    specs: dict = {}

    if cpu := _parse_cpu(title):
        specs["cpu"] = cpu

    storage_gb, storage_type = _parse_storage(title)
    if storage_gb is not None:
        specs["storage_gb"] = storage_gb
        specs["storage_type"] = storage_type

    if ram := _RAM.search(title):
        specs["ram_gb"] = int(ram.group(1) or ram.group(2))
    else:
        for number, unit in _GB.findall(title):
            gb = _to_gb(number, unit)
            if unit.lower() == "gb" and gb in _RAM_SIZES and gb != specs.get("storage_gb"):
                specs["ram_gb"] = gb
                break

    if screen := _parse_screen(title):
        specs["screen_in"] = screen

    return specs


def parse_headphone(title: str) -> dict:
    low = _ascii(title)
    specs: dict = {}

    if "over-ear" in low or "over ear" in low:
        specs["type"] = "over-ear"
    elif "on-ear" in low or "on ear" in low:
        specs["type"] = "on-ear"
    elif any(t in low for t in ["in-ear", "in ear", "intra-auricular", "intra auricular"]):
        specs["type"] = "in-ear"
    elif any(t in low for t in ["earbud", "eardbud", "tws", "buds"]):
        specs["type"] = "earbuds"
    elif "headset" in low or "headphone" in low:
        specs["type"] = "over-ear"

    # anc é boolean: ausência de menção = False (nunca "desconhecido").
    specs["anc"] = any(
        t in low
        for t in [
            "anc",
            "cancelamento de ruido",
            "noise cancel",
            "antiruido",
            "anti ruido",
            "antirruido",
        ]
    )

    if m := _HP_BATTERY.search(low):
        horas = int(m.group(1))
        if 2 <= horas <= 200:
            specs["battery_h"] = horas

    if m := _HP_BLUETOOTH.search(low):
        specs["bluetooth"] = m.group(1)

    if "microfone" in low or re.search(r"\bmic\b", low):
        specs["microphone"] = True

    return specs


def parse_title(category: str, title: str) -> dict:
    parsers = {"notebooks": parse_notebook, "headphones": parse_headphone}
    parser = parsers.get(category)
    return parser(title) if parser else {}
