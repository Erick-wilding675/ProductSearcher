"""Seed-builder (ferramenta de dev, fora do runtime do worker).

Converte o CSV de listagem do Apify no dataset seed YAML (formato `RawProduct`),
extraindo specs do título e enriquecendo com a API do Mercado Livre quando há token.
Ver README.md e ADR-0001/ADR-0005.
"""
