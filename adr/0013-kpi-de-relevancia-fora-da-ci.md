# ADR-0013. O KPI de relevância sai da CI enquanto os rótulos não forem reproduzíveis

- **Status:** Aceito, com gatilho de revisão explícito
- **Data:** 2026-09-19
- **Decisor(es):** Erick (tech lead)

## Contexto

A CI está vermelha na `main` desde **28/08/2026**, sempre no mesmo passo: `pytest` do job
`api`. O diagnóstico, reproduzido localmente contra um Postgres igual ao da CI (pgvector,
migrations, seed):

```
precisão média@5: 0% (alvo 60%, acaso 28%)
  jogos            notebook para jogos       0/0   0%   28%   total 0
  edição de vídeo  notebook para edicao...   0/0   0%   20%   total 0
  ... (10 de 10 casos com total 0)
7 failed, 258 passed
```

**Todas as consultas de caso de uso devolvem zero resultados**, e com elas caem três
consultas de `test_relevance.py` que contêm "gamer", mais o controle "termo no título".

A causa não é a busca. Desde o [ADR-0010](0010-fase-6-onde-a-ia-entra.md) D2, o
`RuleBasedIntentParser` converte necessidade ("gamer", "para jogos") em **filtro duro** de
`use_case` sobre `product_specs.attributes`. Os rótulos que esse filtro procura são
produzidos por **LLM offline** e gravados direto no banco: eles **não estão no seed
versionado**. Um catálogo recém-carregado pela ingestão não tem rótulo nenhum, então o
filtro não casa com nada.

O problema real, do qual a CI vermelha é só o sintoma mais visível: **os rótulos não são
reproduzíveis a partir do repositório.** O mesmo defeito já apareceu duas vezes:

1. Recarregar o seed apagava os rótulos em silêncio, porque o upsert substituía
   `attributes` inteiro (corrigido para merge, ADR-0010).
2. A recriação do banco em `sa-east-1` derrubou a busca por "notebook gamer" em produção
   até alguém rodar a re-rotulagem à mão (ADR-0011).

Em todos os casos a falha é **silenciosa**: consulta de uma palavra responde, consulta com
necessidade volta vazia.

## Decisão

**D1. A suíte pula a consulta que depende de `use_case` quando o catálogo não tem
rótulos.** O helper `pula_sem_rotulo_de_uso` (em `api/tests/conftest.py`) parseia a
consulta e, se o intent contém `use_case` e o catálogo carregado tem zero rótulos, chama
`pytest.skip` com a razão e o comando que resolve.

O critério é **por consulta**, não por arquivo. Consulta que não vira filtro de `use_case`
continua sendo medida normalmente, mesmo num catálogo sem rótulo.

**D2. Os dois agregados pulam inteiros, não parcialmente.** `test_relevancia_top5`,
`test_cobertura_casos_de_uso` e `test_precisao_casos_de_uso` pulam se **qualquer** consulta
sua depender de rótulo ausente. Medir o agregado sobre o subconjunto que sobrou mudaria o
denominador, e o número deixaria de ser comparável com o histórico registrado no ADR-0010
(27% para 55% para 100% de cobertura@5). Um KPI que muda de definição em silêncio é pior
que um KPI ausente.

**D3. Pular é a decisão, e o custo fica registrado aqui.** Isto **desfaz na prática** uma
decisão deliberada do ADR-0010 D1: o serviço Postgres foi adicionado ao job `api` da CI
exatamente para que o KPI de relevância do PRD fosse medido **em todo merge**, em vez de
só na máquina do dev. Com D1 e D2, ele volta a não ser medido em merge nenhum.

Não é um empate. É a troca de um sinal vermelho permanente e sem informação (que treina o
time a ignorar a CI) por um sinal verde honesto mais uma lacuna declarada. A lacuna está
escrita no `skip`, no `conftest.py`, no `api/README.md` e aqui.

## Benefícios

- A `main` volta a ficar verde, e um vermelho futuro volta a significar alguma coisa.
- O deploy automático destrava: ele depende de `workflow_run` da CI com sucesso
  (ADR-0011 D8), então com a CI vermelha nenhum push publicava.
- O skip **nomeia a causa e a correção**, em vez de esconder: a mensagem diz que a consulta
  vira filtro de `use_case`, que o catálogo não tem rótulos e qual comando os produz.
- O guard é preciso nos dois sentidos, verificado: sem rótulos, 248 passam e 24 pulam, zero
  falham; com os 213 rótulos de produção copiados para o banco de teste, 265 passam, nada
  pula por essa causa e os dois agregados do KPI rodam e ficam **verdes**.

## Consequências negativas

- **O KPI de relevância deixa de ser verificado em merge.** Uma regressão de relevância
  passa pela CI sem ser notada. Esta é a consequência principal e não tem mitigação dentro
  desta decisão.
- **O verde da CI passa a dizer menos do que parece.** Quem olhar o badge não sabe que a
  medida mais importante da busca está pulada. Por isso o `api/README.md` marca a suíte
  como condicional.
- **A lacuna tende a se normalizar.** Skip que ninguém revisita vira teste morto. O gatilho
  abaixo existe para impedir isso, e depende de alguém olhar.
- Medir o KPI passa a exigir passo manual: carregar o seed e rodar o rotulador, com chave
  da Groq e cerca de 25 minutos.

## Alternativas descartadas

| Alternativa | Por que não agora |
| --- | --- |
| **Versionar os rótulos no seed** (exportar os 213 para `seed/products/*.yaml` como spec comum) | É a correção de raiz e resolveria os três sintomas de uma vez: CI mede o KPI de verdade, recarregar o seed deixa de apagar rótulo, e o passo manual sai do runbook de recriação do banco. Adiada por decisão do tech lead: muda dado versionado e exige emenda ao ADR-0010 D2, que trata os rótulos como dado derivado de banco. **É a evolução preferida quando houver espaço.** |
| Rodar o rotulador dentro da CI | Mede o KPI de verdade, mas põe `GROQ_API_KEY` como secret de CI, acrescenta cerca de 25 min a cada execução e faz a CI depender de serviço externo e de rate limit. Caro e frágil para rodar em toda PR. |
| Deixar a CI vermelha | Vermelho permanente não é sinal, é ruído. Some com a capacidade de detectar a próxima quebra de verdade, e trava o deploy automático. |
| Baixar as metas até passarem | Transformaria o KPI num número que sempre passa. Pior que não medir, porque parece medição. |

## Caminho de evolução / gatilho de revisão

- **Gatilho principal:** qualquer trabalho que toque relevância, ranking ou `IntentParser`.
  Antes de mexer, rode a suíte com rótulos (seed mais `label_use_cases`, ou copiando os
  rótulos de produção para o banco de teste) e registre o número. Sem isso, a mudança não
  tem linha de base.
- **Gatilho para versionar os rótulos no seed:** a segunda vez que a ausência de rótulo
  custar tempo de alguém, ou a próxima recriação de banco. Duas ocorrências já aconteceram
  antes desta ADR; a terceira deve fechar a discussão.
- **Como remover esta ADR:** com os rótulos no seed, `catalogo_tem_use_case` passa a ser
  sempre verdadeiro, `pula_sem_rotulo_de_uso` vira código morto e some junto com este
  documento, que passa a `Substituído`.

## Impacto futuro

- **Testes:** `api/tests/conftest.py` ganha a fixture `catalogo_tem_use_case` e o helper
  `pula_sem_rotulo_de_uso`. `api/tests/test_relevance.py` e
  `api/tests/test_relevance_use_cases.py` passam a consultá-los.
- **CI:** o comentário do job `api` em `.github/workflows/ci.yml` deixa de afirmar que o
  KPI é medido em todo merge, porque deixou de ser verdade.
- **Documentação:** `api/README.md` marca a suíte de relevância como condicional aos
  rótulos, com o comando que os produz.
