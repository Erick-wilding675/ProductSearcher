# Busca vetorial — como rodar (ADR-010 D3)

A busca vetorial é **desligada por padrão** (`VECTOR_ENABLED=false`). Sem ela a
API sobe normal e o FTS serve sozinho — é o mesmo princípio de todo o resto da
IA neste projeto. Este documento é para quando você quiser ligá-la.

## O caminho curto: usar a imagem `:vector`

A imagem padrão **não** traz o modelo, de propósito: são 750 MB e ~10 min de
export que a maioria dos builds não usa. A imagem de deploy é outra, e monta em
cima da padrão:

```bash
docker build -t productsearcher-api ./api
docker build -f api/Dockerfile.vector -t productsearcher-api:vector ./api
```

O segundo build baixa os pesos, exporta para ONNX e quantiza em int8. Ele é
demorado **uma vez**; o cache do Docker cobre as vezes seguintes.

## Carregar os vetores dos produtos

Os vetores dos produtos são gerados **offline, uma vez** — em runtime o único
cálculo é o vetor da consulta (ADR-010 D3). A carga roda dentro do mesmo
processo que serve a API (D3.1), que é o que garante que produto e consulta
caiam no mesmo espaço vetorial:

```bash
docker run --rm \
  -e DATABASE_URL='postgresql+psycopg://postgres:postgres@host.docker.internal:5432/productsearcher' \
  productsearcher-api:vector \
  python -m app.search.vector_load
```

É idempotente: rodar de novo não refaz o que já está feito. Use `--force` para
revetorizar tudo.

> **Se você trocar de modelo, rode a carga de novo.** A carga carimba cada
> produto com o id do modelo que gerou o vetor, e produtos carimbados com outro
> modelo voltam a contar como pendentes. Vetores de modelos diferentes vivem em
> espaços diferentes e a similaridade entre eles não significa nada — não dá
> erro, só piora o resultado.

## Rodar os testes que exercitam o modelo

`tests/test_embedding_real.py` é pulado quando os pesos não estão presentes.
Para exercitá-lo, rode a suíte dentro da imagem `:vector`:

```bash
docker run --rm productsearcher-api:vector \
  sh -c "pip install -q '.[dev]' && pytest -q tests/test_embedding_real.py"
```

Ou, fora do container, aponte `EMBEDDING_MODEL_DIR` para um diretório com os
pesos exportados e instale o extra: `pip install './api[vector]'`.

## Uma nota sobre threads

`embedding_threads` está fixado em **1** no código, e não é preciosismo: medido
no ADR-010 D3.3, em 1 vCPU com o pool de threads no default o p95 vai a 804 ms e
fura a RNF-01 sozinho, antes da query SQL. O runtime dimensiona o pool pelas
CPUs que *enxerga*, não pelas que o cgroup concede.

Só faz sentido subir esse número num host com vários vCPUs dedicados à API — e
aí vale medir de novo, não estimar.
