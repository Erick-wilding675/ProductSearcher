// Popup da action: mostra o top-N para a busca da aba atual (RF-52).
//
// Lê a URL da aba com `activeTab`, permissão concedida só no clique do usuário — a
// extensão não enxerga o histórico nem as outras abas.

import { TOP_N, WEB_APP_URL } from "../shared/config.js";
import { queryDaSerp } from "../shared/coverage.js";

const conteudo = document.getElementById("conteudo");

function el(tag, className, texto) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (texto != null) node.textContent = texto;
  return node;
}

function render(...nodes) {
  conteudo.replaceChildren(...nodes);
  conteudo.setAttribute("aria-busy", "false");
}

function formatarPreco(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function estado(texto, dica) {
  const bloco = el("div", "estado");
  bloco.appendChild(el("p", null, texto));
  if (dica) bloco.appendChild(el("p", "dica", dica));
  return bloco;
}

function linkWebApp(query) {
  const link = el("a", "link", "Ver todos no ProductSearcher →");
  link.href = query
    ? `${WEB_APP_URL}/?q=${encodeURIComponent(query)}`
    : WEB_APP_URL;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function montarLista(results) {
  const lista = el("ul", "lista");
  results.forEach((item, i) => {
    const card = el("li", "card");
    card.appendChild(el("span", "posicao", String(i + 1)));

    const corpo = el("div", "corpo");
    corpo.appendChild(el("p", "nome", item.name));
    const meta = el("div", "meta");
    if (item.brand) meta.appendChild(el("span", "marca", item.brand));
    meta.appendChild(el("span", "preco", formatarPreco(item.min_price)));
    corpo.appendChild(meta);

    card.appendChild(corpo);
    lista.appendChild(card);
  });
  return lista;
}

async function abaAtual() {
  const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
  return aba;
}

async function main() {
  const aba = await abaAtual();
  const query = queryDaSerp(aba?.url || "");

  if (!query) {
    render(
      estado(
        "Abra uma busca no Google para ver sugestões.",
        "A extensão só age na página de resultados do Google.",
      ),
      linkWebApp(null),
    );
    return;
  }

  const cobertura = await chrome.runtime.sendMessage({
    type: "coverage",
    query,
  });
  if (!cobertura?.category) {
    render(
      estado(
        `Ainda não cobrimos "${query}".`,
        "O catálogo hoje tem notebooks e fones de ouvido.",
      ),
      linkWebApp(null),
    );
    return;
  }

  const resposta = await chrome.runtime.sendMessage({
    type: "topProducts",
    query,
    category: cobertura.category,
    limit: TOP_N,
  });

  if (!resposta?.ok) {
    render(
      estado(
        "Não consegui falar com a API.",
        "Confira se o backend está no ar.",
      ),
      linkWebApp(query),
    );
    return;
  }
  if (!resposta.results.length) {
    render(estado(`Nenhum produto para "${query}".`), linkWebApp(query));
    return;
  }

  render(
    el("p", "titulo", `Top ${resposta.results.length} para "${query}"`),
    montarLista(resposta.results),
    linkWebApp(query),
  );
}

main().catch((erro) => {
  console.error("[ProductSearcher] popup:", erro);
  render(estado("Algo deu errado.", erro.message));
});
