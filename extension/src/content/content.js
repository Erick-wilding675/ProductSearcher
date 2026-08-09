// Content script da SERP do Google.
//
// Fluxo: lê a busca da URL -> pergunta ao service worker se a categoria é coberta ->
// só então pede o top-N e injeta o painel. Fora de cobertura, não faz nada e não
// manda nada para a API (RF-51, RNF-09).
//
// Não chamamos a API daqui: o fetch sairia com origem google.com e tomaria CORS.
// Toda rede passa pelo service worker.

const PREFIXO = "ps-"; // classes prefixadas: a SERP é território alheio
const ID_PAINEL = "ps-painel";
const ID_BOTAO = "ps-botao-flutuante";

/** Âncoras onde o painel cabe, da melhor para a pior. */
const ANCORAS = [
  "#rhs", // coluna direita (knowledge panel) — não briga com os resultados
  "#rcnt #center_col", // topo da coluna de resultados
  "#search",
];

function el(tag, className, texto) {
  const node = document.createElement(tag);
  if (className) node.className = PREFIXO + className;
  if (texto != null) node.textContent = texto; // textContent, nunca innerHTML
  return node;
}

function formatarPreco(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function montarCard(item, indice) {
  const card = el("li", "card");
  card.appendChild(el("span", "posicao", String(indice + 1)));

  const corpo = el("div", "corpo");
  corpo.appendChild(el("p", "nome", item.name));

  const meta = el("div", "meta");
  if (item.brand) meta.appendChild(el("span", "marca", item.brand));
  meta.appendChild(el("span", "preco", formatarPreco(item.min_price)));
  corpo.appendChild(meta);

  card.appendChild(corpo);
  return card;
}

function montarPainel({ query, results, webAppUrl }) {
  const painel = el("aside", "painel");
  painel.id = ID_PAINEL;
  // A SERP é conteúdo de terceiro: deixamos explícito de onde vem este bloco.
  painel.setAttribute("role", "complementary");
  painel.setAttribute("aria-label", "Sugestões do ProductSearcher");

  const cabecalho = el("header", "cabecalho");
  cabecalho.appendChild(el("span", "marca-logo", "ProductSearcher"));
  const fechar = el("button", "fechar", "×");
  fechar.type = "button";
  fechar.setAttribute("aria-label", "Fechar sugestões do ProductSearcher");
  fechar.addEventListener("click", () => painel.remove());
  cabecalho.appendChild(fechar);
  painel.appendChild(cabecalho);

  painel.appendChild(
    el("p", "titulo", `Top ${results.length} para "${query}"`),
  );

  const lista = el("ul", "lista");
  results.forEach((item, i) => lista.appendChild(montarCard(item, i)));
  painel.appendChild(lista);

  const link = el("a", "link", "Ver todos no ProductSearcher →");
  link.href = webAppUrl;
  link.target = "_blank";
  link.rel = "noopener noreferrer"; // sem window.opener para a página aberta
  painel.appendChild(link);

  return painel;
}

/** Insere o painel na primeira âncora existente. `false` quando nenhuma serve. */
function injetar(painel) {
  for (const seletor of ANCORAS) {
    const alvo = document.querySelector(seletor);
    if (alvo) {
      alvo.prepend(painel);
      return true;
    }
  }
  return false;
}

/**
 * Fallback quando a injeção falha (RF-53).
 *
 * O layout do Google muda sem aviso e sem contrato — quando nenhuma âncora existe, um
 * botão fixo é melhor que sumir em silêncio: o usuário ainda alcança o resultado.
 */
function botaoFlutuante(dados) {
  if (document.getElementById(ID_BOTAO)) return;

  const botao = el(
    "button",
    "flutuante",
    `Top ${dados.results.length} no ProductSearcher`,
  );
  botao.id = ID_BOTAO;
  botao.type = "button";
  botao.addEventListener("click", () => {
    const existente = document.getElementById(ID_PAINEL);
    if (existente) {
      existente.remove();
      return;
    }
    const painel = montarPainel(dados);
    painel.classList.add(PREFIXO + "painel-flutuante");
    document.body.appendChild(painel);
  });
  document.body.appendChild(botao);
}

function limpar() {
  document.getElementById(ID_PAINEL)?.remove();
  document.getElementById(ID_BOTAO)?.remove();
}

async function enviar(mensagem) {
  try {
    return await chrome.runtime.sendMessage(mensagem);
  } catch {
    return null; // service worker reciclado ou extensão recarregada
  }
}

// Entre a limpeza e a injeção há idas ao service worker. Se o usuário troca de busca
// nesse meio-tempo, duas execuções se sobrepõem e a mais lenta injetaria o resultado
// da busca anterior. Cada execução carimba a sua geração e desiste se outra começou.
let geracao = 0;

async function avaliarPagina() {
  const minha = ++geracao;
  const atual = () => minha === geracao;

  limpar();

  const { queryDaSerp } = await import(
    chrome.runtime.getURL("src/shared/coverage.js")
  );
  const query = queryDaSerp(location.href);
  if (!query || !atual()) return;

  const cobertura = await enviar({ type: "coverage", query });
  if (!cobertura?.category || !atual()) return; // fora de cobertura: silêncio (RF-51)

  const resposta = await enviar({
    type: "topProducts",
    query,
    category: cobertura.category,
  });
  if (!resposta?.ok || !resposta.results?.length || !atual()) return;

  const dados = {
    query,
    results: resposta.results,
    webAppUrl: await urlDoWebApp(query),
  };
  if (!atual()) return;

  const painel = montarPainel(dados);
  if (!injetar(painel)) botaoFlutuante(dados);
}

/** Link para o web app com a busca já preenchida (RF-54). */
async function urlDoWebApp(query) {
  const { WEB_APP_URL } = await import(
    chrome.runtime.getURL("src/shared/config.js")
  );
  return `${WEB_APP_URL}/?q=${encodeURIComponent(query)}`;
}

// O Google troca de busca sem recarregar a página, então `document_idle` roda uma vez
// só. Observar a URL mantém o painel coerente com a busca que está na tela.
let urlAtual = location.href;
new MutationObserver(() => {
  if (location.href !== urlAtual) {
    urlAtual = location.href;
    avaliarPagina();
  }
}).observe(document.body, { childList: true, subtree: true });

avaliarPagina();
