"""Ranking determinístico e explicável (RF-30/31).

Recebe os candidatos do `SearchProvider` (retrieval) e produz uma ordenação
**reproduzível** por critérios objetivos, devolvendo — junto de cada item — o porquê
da posição. Nenhuma IA envolvida: o mesmo input gera sempre o mesmo output (princípio
do projeto). Ver ADR-0007.

Modelo de score (soma ponderada, só sobre os fatores aplicáveis ao intent):

    relevance  peso 0.6  relevância textual (fts_rank normalizado no conjunto)
    price      peso 0.3  aderência ao teto de preço (mais barato dentro do orçamento
                         pontua mais; acima do teto zera)
    attributes peso 0.1  cobertura dos atributos pedidos no intent

Fatores não aplicáveis (ex.: sem `price_max`, sem `attributes`) saem da conta e os
pesos são renormalizados, para não penalizar consultas sem aquele sinal.
"""

from typing import Protocol

from app.search.intent import Intent

WEIGHTS = {"relevance": 0.6, "price": 0.3, "attributes": 0.1}


class RankingService(Protocol):
    def rank(self, hits: list[dict], intent: Intent) -> dict: ...


class DeterministicRanking:
    """Ordenação reproduzível por critérios objetivos; retorna itens + critérios."""

    def rank(self, hits: list[dict], intent: Intent) -> dict:
        criteria = _criteria(intent)
        if not hits:
            return {"criteria": criteria, "items": []}

        max_rank = max((float(h.get("fts_rank") or 0.0) for h in hits), default=0.0)

        scored = []
        for h in hits:
            factors = _factors(h, intent, max_rank)
            score = _weighted_score(factors)
            scored.append({**h, "score": round(score, 6), "factors": factors})

        # Ordenação determinística: score desc, depois desempate estável e objetivo
        # (relevância desc, nome asc, id asc) — nunca depende da ordem de chegada.
        scored.sort(
            key=lambda it: (
                -it["score"],
                -float(it.get("fts_rank") or 0.0),
                str(it.get("name") or ""),
                str(it.get("id") or ""),
            )
        )
        return {"criteria": criteria, "items": scored}


def _factors(hit: dict, intent: Intent, max_rank: float) -> dict:
    """Score de cada fator no intervalo [0,1] + se é aplicável ao intent."""
    factors: dict = {}

    # Relevância textual: normalizada pelo maior fts_rank do conjunto.
    rel = float(hit.get("fts_rank") or 0.0)
    factors["relevance"] = {
        "score": (rel / max_rank) if max_rank > 0 else 0.0,
        "applicable": max_rank > 0,
    }

    # Preço: só aplicável quando há teto no intent E o item tem preço.
    price = hit.get("min_price")
    if intent.price_max is not None and price is not None:
        pmax = float(intent.price_max)
        price = float(price)
        fit = (pmax - price) / pmax if pmax > 0 else 0.0
        factors["price"] = {"score": _clamp(fit), "applicable": True}
    else:
        factors["price"] = {"score": 0.0, "applicable": False}

    # Atributos: cobertura dos pedidos no intent presentes/casados no item.
    wanted = intent.attributes or {}
    if wanted:
        have = hit.get("attributes") or {}
        matched = sum(1 for k, v in wanted.items() if _attr_matches(have.get(k), v))
        factors["attributes"] = {"score": matched / len(wanted), "applicable": True}
    else:
        factors["attributes"] = {"score": 0.0, "applicable": False}

    return factors


def _weighted_score(factors: dict) -> float:
    """Soma ponderada só sobre fatores aplicáveis, com renormalização dos pesos."""
    total_w = sum(WEIGHTS[name] for name, f in factors.items() if f["applicable"])
    if total_w == 0:
        return 0.0
    return (
        sum(WEIGHTS[name] * f["score"] for name, f in factors.items() if f["applicable"]) / total_w
    )


def _criteria(intent: Intent) -> list[dict]:
    """Descreve os critérios ativos (o 'porquê' da ordenação), para a UI/RF-31."""
    active = {
        "relevance": bool(intent.raw),
        "price": intent.price_max is not None,
        "attributes": bool(intent.attributes),
    }
    labels = {
        "relevance": "Relevância textual (Postgres FTS)",
        "price": "Aderência ao teto de preço",
        "attributes": "Cobertura dos atributos pedidos",
    }
    return [
        {
            "factor": name,
            "weight": WEIGHTS[name],
            "active": active[name],
            "description": labels[name],
        }
        for name in ("relevance", "price", "attributes")
    ]


def _attr_matches(have, want) -> bool:
    """Casamento de atributo tolerante a tipo (string/num/bool), case-insensitive."""
    if have is None:
        return False
    if isinstance(want, bool) or isinstance(have, bool):
        return bool(have) == bool(want)
    return str(have).strip().lower() == str(want).strip().lower()


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
