// Testes da decisão de cobertura e da captura da query (RF-50/51).
// Runner nativo do Node (`node --test`) — sem dependência nova no projeto.

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  categoriaDaBusca,
  normalizar,
  palavrasChave,
  queryDaSerp,
} from "../src/shared/coverage.js";

// Igual ao que `GET /categories` devolve.
const CATEGORIAS = [
  { slug: "headphones", name: "Fones de ouvido", product_count: 71 },
  { slug: "notebooks", name: "Notebooks", product_count: 96 },
];

describe("normalizar", () => {
  it("tira acento e caixa", () => {
    assert.equal(normalizar("Fones de OUVIDO"), "fones de ouvido");
    assert.equal(normalizar("Preço Ótimo Ação"), "preco otimo acao");
  });

  it("tolera vazio e nulo", () => {
    assert.equal(normalizar(""), "");
    assert.equal(normalizar(null), "");
  });
});

describe("palavrasChave", () => {
  it("deriva os termos do slug e do nome vindos da API", () => {
    const mapa = palavrasChave(CATEGORIAS);
    assert.ok(mapa.get("headphones").includes("ouvido")); // veio do nome
    assert.ok(mapa.get("notebooks").includes("notebooks")); // veio do slug
  });

  it("descarta palavras curtas e conectivos", () => {
    const termos = palavrasChave(CATEGORIAS).get("headphones");
    assert.ok(!termos.includes("de"));
    assert.ok(termos.every((t) => t.length >= 4));
  });

  it("inclui sinonimos que nao aparecem no nome da categoria", () => {
    const termos = palavrasChave(CATEGORIAS).get("headphones");
    assert.ok(termos.includes("headset"));
    assert.ok(termos.includes("fone"));
  });
});

describe("categoriaDaBusca", () => {
  const casos = [
    ["melhor notebook gamer", "notebooks"],
    ["notebooks para trabalho", "notebooks"],
    ["laptop barato", "notebooks"],
    ["fone bluetooth", "headphones"],
    ["fones de ouvido sem fio", "headphones"],
    ["headset gamer", "headphones"],
    ["earbuds tws", "headphones"],
  ];

  for (const [query, esperado] of casos) {
    it(`reconhece ${JSON.stringify(query)}`, () => {
      assert.equal(categoriaDaBusca(query, CATEGORIAS), esperado);
    });
  }

  it("casa singular e plural", () => {
    assert.equal(categoriaDaBusca("notebook", CATEGORIAS), "notebooks");
    assert.equal(categoriaDaBusca("notebooks", CATEGORIAS), "notebooks");
  });

  it("ignora caixa e acento", () => {
    assert.equal(categoriaDaBusca("FONES DE OUVIDO", CATEGORIAS), "headphones");
  });

  it("vence o termo mais a esquerda", () => {
    // Mesma regra do parser do backend, para os dois nao discordarem.
    assert.equal(
      categoriaDaBusca("fone para notebook", CATEGORIAS),
      "headphones",
    );
    assert.equal(
      categoriaDaBusca("notebook com fone", CATEGORIAS),
      "notebooks",
    );
  });

  it("fica fora de cobertura no que o catalogo nao tem", () => {
    // O silencio e o comportamento certo: a SERP nao e nossa (RF-51).
    assert.equal(categoriaDaBusca("receita de bolo", CATEGORIAS), null);
    assert.equal(categoriaDaBusca("tenis nike 42", CATEGORIAS), null);
    assert.equal(categoriaDaBusca("", CATEGORIAS), null);
  });

  it("sem categorias conhecidas, nao ativa", () => {
    // API fora: melhor ficar calado do que injetar UI sem dado.
    assert.equal(categoriaDaBusca("notebook", []), null);
    assert.equal(categoriaDaBusca("notebook", null), null);
  });
});

describe("queryDaSerp", () => {
  it("le o parametro q da busca do Google", () => {
    assert.equal(
      queryDaSerp("https://www.google.com/search?q=melhor+notebook&hl=pt-BR"),
      "melhor notebook",
    );
    assert.equal(
      queryDaSerp("https://www.google.com.br/search?q=fone%20anc"),
      "fone anc",
    );
  });

  it("ignora dominio que nao e do Google", () => {
    assert.equal(queryDaSerp("https://www.bing.com/search?q=notebook"), null);
    assert.equal(queryDaSerp("https://googleblog.com/search?q=notebook"), null);
  });

  it("ignora paginas do Google que nao sao a SERP", () => {
    assert.equal(queryDaSerp("https://www.google.com/maps?q=cafe"), null);
    assert.equal(queryDaSerp("https://www.google.com/"), null);
  });

  it("devolve null sem query ou com URL invalida", () => {
    assert.equal(queryDaSerp("https://www.google.com/search?q="), null);
    assert.equal(queryDaSerp("https://www.google.com/search"), null);
    assert.equal(queryDaSerp("about:blank"), null);
    assert.equal(queryDaSerp(""), null);
  });

  it("nao le nada da pagina alem do parametro q (RNF-09)", () => {
    // A URL da SERP carrega bem mais que a busca; so `q` sai daqui.
    const url =
      "https://www.google.com/search?q=fone&ei=SESSAO&uact=5&sclient=gws-wiz";
    assert.equal(queryDaSerp(url), "fone");
  });
});
