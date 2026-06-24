"""Testes do IntentParser (Fase 3, RF-11). Placeholder até a implementação."""

import pytest

from app.search.intent import RuleBasedIntentParser


@pytest.mark.skip(reason="TODO Fase 3: implementar RuleBasedIntentParser")
def test_parses_category_and_price() -> None:
    parser = RuleBasedIntentParser()
    intent = parser.parse("melhor notebook até R$5000")
    assert intent.category == "notebook"
    assert intent.price_max == 5000
