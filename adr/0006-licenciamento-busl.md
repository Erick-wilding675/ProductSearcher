# ADR-0006 — Licenciamento: Business Source License 1.1

- **Status:** Aceito
- **Data:** 2026-07-01
- **Decisor:** Erick Cardoso Mendes

## Contexto

O ProductSearcher é público (portfólio), mas queremos **proteger o uso comercial** por um período e, ao mesmo tempo, sinalizar que o projeto **se tornará aberto no futuro**. Licenças permissivas (MIT/Apache) liberam uso comercial imediato; copyleft (GPL) não impede SaaS comercial; "all rights reserved" não prevê abertura futura. Precisamos de um meio-termo: código visível, uso livre para avaliação/estudo, restrição comercial temporária e conversão automática para open source.

## Decisão

Adotar a **Business Source License 1.1 (BUSL-1.1)** com os parâmetros:

- **Licensor:** Erick Cardoso Mendes
- **Licensed Work:** ProductSearcher © 2026
- **Additional Use Grant:** uso em produção permitido **desde que não-comercial**
- **Change Date:** **2030-07-01** (4 anos)
- **Change License:** **Apache License 2.0**

Na Change Date, o trabalho passa automaticamente a ser licenciado sob Apache 2.0.

## Benefícios

- **Código aberto à leitura** (bom para portfólio) sem liberar uso comercial imediato.
- Uso livre para **avaliação, desenvolvimento e teste** (não-produção) e uso **não-comercial** em produção.
- **Abertura garantida no futuro** (Apache 2.0 na Change Date) — evita o estigma de "código fechado".
- Modelo conhecido e defensável (usado por diversas empresas de infraestrutura).

## Consequências negativas

- **Não é uma licença OSI open-source**; o GitHub não exibe selo padrão (mostra "Other"/BUSL).
- Pode **afastar contribuidores** que só trabalham com licenças OSI.
- Ferramentas/empresas com políticas restritas a OSI podem evitar a dependência.
- Exige atenção ao **texto exato** e aos parâmetros (não modificar o corpo da licença, conforme os *Covenants*).

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| MIT / Apache 2.0 (permissivas) | Liberam uso comercial imediato — sem a proteção desejada. **Descartado (mas Apache 2.0 é a licença de conversão).** |
| GPLv3 (copyleft) | Não impede uso comercial em SaaS; foco é reciprocidade, não restrição comercial. **Descartado.** |
| Proprietária / all rights reserved | Sem compromisso de abertura futura; menos atrativo para portfólio. **Descartado.** |

## Caminho de evolução / gatilho de revisão

A licença **converte-se sozinha** para Apache 2.0 na Change Date (2030-07-01). O Licensor pode **relicenciar antes** se quiser. Revisar se: (a) o projeto buscar contribuição externa ampla (talvez migrar antes para OSI), ou (b) a estratégia comercial mudar. Cada versão publicada pode ter sua própria Change Date.

## Impacto futuro

Arquivo `LICENSE` na raiz e seção "Licença" no `README`. Ao aproximar-se da Change Date, avaliar comunicação da transição para Apache 2.0.
