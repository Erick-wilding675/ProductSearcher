// Service worker: o único ponto que fala com a API.
//
// Content script e popup mandam mensagem para cá em vez de chamar a API direto —
// o content script sairia com a origem do google.com e tomaria bloqueio de CORS, e
// centralizar aqui faz os dois compartilharem o mesmo cache de cobertura.

import { getCategories, search } from "../shared/api.js";
import { COVERAGE_TTL_MS, TOP_N } from "../shared/config.js";
import { categoriaDaBusca } from "../shared/coverage.js";

const CHAVE_CACHE = "coverage";

/**
 * Categorias cobertas, com cache de TTL curto.
 *
 * Em caso de falha devolve `[]`, não lança: sem cobertura conhecida a extensão fica
 * calada, que é o comportamento certo quando a API está fora (a SERP não é nossa).
 */
async function categoriasCobertas() {
  const guardado = await chrome.storage.local.get(CHAVE_CACHE);
  const cache = guardado[CHAVE_CACHE];
  if (cache && Date.now() - cache.gravadoEm < COVERAGE_TTL_MS) {
    return cache.categorias;
  }
  try {
    const categorias = await getCategories();
    await chrome.storage.local.set({
      [CHAVE_CACHE]: { categorias, gravadoEm: Date.now() },
    });
    return categorias;
  } catch (erro) {
    console.warn("[ProductSearcher] /categories indisponível:", erro.message);
    // Cache vencido ainda é melhor que nada enquanto a API não volta.
    return cache?.categorias || [];
  }
}

/** A busca cai em categoria coberta? Responde o slug ou `null` (RF-51). */
async function verificarCobertura(query) {
  const categorias = await categoriasCobertas();
  return { category: categoriaDaBusca(query, categorias) };
}

/**
 * Top-N para a busca — só é chamado depois da cobertura confirmar (RF-52).
 * Assim a consulta só sai do navegador quando há chance real de ser útil.
 */
async function buscarTopN({ query, category, limit = TOP_N }) {
  try {
    const { results, total } = await search(query, { category, limit });
    return { ok: true, results, total };
  } catch (erro) {
    return { ok: false, error: erro.message };
  }
}

const HANDLERS = {
  coverage: (msg) => verificarCobertura(msg.query),
  topProducts: (msg) => buscarTopN(msg),
};

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const handler = HANDLERS[msg?.type];
  if (!handler) return false;
  // `true` mantém o canal aberto para a resposta assíncrona (contrato do MV3).
  handler(msg)
    .then(sendResponse)
    .catch((erro) => sendResponse({ ok: false, error: erro.message }));
  return true;
});

// Cobertura muda com a ingestão do catálogo, não com o uso: buscar na instalação
// evita que a primeira SERP do usuário pague a latência.
chrome.runtime.onInstalled.addListener(() => {
  categoriasCobertas().catch(() => {});
});
