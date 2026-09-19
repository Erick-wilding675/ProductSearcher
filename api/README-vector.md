# Busca vetorial: como ligar e rodar

> Referência: [ADR-0010](../adr/0010-fase-6-onde-a-ia-entra.md) D3 e D4.

A busca vetorial é **desligada por padrão** (`VECTOR_ENABLED=false`), e o motivo não é
cautela genérica: medida contra a suíte de relevância da Fase 6, a união vetorial mais
textual deu **precisão@5 de 64% contra 68% do FTS sozinho**. O braço vetorial acerta a
categoria e erra a spec. O caminho inteiro (embedder, provider, carga, imagem) está
construído e testado, esperando a tabela `searches` acumular consulta real de produção,
porque é justamente nas consultas imprevistas (erro de digitação, sinônimo, formulação
torta) que ele plausivelmente ajuda, e uma suíte de 10 casos curados não tem nenhuma
delas.

Este documento é para quando você quiser ligá-la. **Ligue só com medição nova por cima.**

## A imagem `:vector`

A imagem padrão **não** traz o modelo, de propósito: em produção o backend precisa caber em
256 MB, e o modelo não é usado. A imagem pesada monta em cima da padrão:

```bash
docker build -t productsearcher-api ./api
docker build -f api/Dockerfile.vector -t productsearcher-api:vector ./api
```

O segundo build baixa os pesos, exporta para ONNX e quantiza em int8. Demora **uma vez**;
o cache do Docker cobre as seguintes.

O custo dela são dois números, não um (ADR-0010 D3.4): **404 MB** para puxar e **886 MB**
em disco. Confundir os dois foi o que obrigou a remedir e a corrigir o comunicado de
requisitos de host.

## Carregar os vetores dos produtos

Os vetores dos produtos são gerados **offline, uma vez**. Em runtime o único cálculo é o
vetor da consulta. A carga roda dentro do mesmo processo que serve a API, e é isso que
garante que produto e consulta caiam no mesmo espaço vetorial:

```bash
docker run --rm \
  -e DATABASE_URL='postgresql+psycopg://postgres:postgres@host.docker.internal:5432/productsearcher' \
  productsearcher-api:vector \
  python -m app.search.vector_load
```

É idempotente: rodar de novo não refaz o que já está feito. Use `--force` para revetorizar
tudo.

> **Trocou de modelo? Rode a carga de novo.** Cada produto é carimbado em
> `product_specs.attributes._embedding` com o id do modelo que gerou o vetor, e produto
> carimbado por outro modelo volta a contar como pendente. Vetores de modelos diferentes
> vivem em espaços diferentes e a similaridade entre eles não significa nada: não dá erro,
> só piora o resultado em silêncio.

A carga escreve o carimbo com merge (`||`), nunca substituindo `attributes`. Substituir
apagaria os rótulos de `use_case`, que moram na mesma coluna.

### Contra o Supabase

A carga em produção (28/08/2026) levou 3 minutos para 235 produtos, com lote de 1, rodando
dentro da imagem `:vector` e falando com o Supabase pelo **pooler em modo sessão**. A
conexão direta é IPv6-only e o Docker não a alcança.

## Testes que exercitam o modelo

`tests/test_embedding_real.py` é pulado quando os pesos não estão presentes. Para
exercitá-lo:

```bash
docker run --rm productsearcher-api:vector \
  sh -c "pip install -q '.[dev]' && pytest -q tests/test_embedding_real.py"
```

Fora do container, aponte `EMBEDDING_MODEL_DIR` para um diretório com os pesos exportados e
instale o extra: `pip install './api[vector]'`.

## A nota sobre threads

`EMBEDDING_THREADS` está fixado em **1** no código, e não é preciosismo. Medido no ADR-0010
D3.3: em 1 vCPU, com o pool de threads no default, o p95 vai a **804 ms** e fura a RNF-01
sozinho, antes mesmo da query SQL. O runtime dimensiona o pool pelas CPUs que **enxerga**,
não pelas que o cgroup concede.

Subir esse número só faz sentido num host com vários vCPUs dedicados à API, e aí vale medir
de novo em vez de estimar.
