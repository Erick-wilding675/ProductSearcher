// Cliente da API do ProductSearcher.
//
// IMPORTANTE: só use isto no **service worker**. Fetch feito de um content script sai
// com a origem da página (google.com), que o CORS da API não libera — o regex do
// backend só aceita `chrome-extension://`. Content script e popup falam com o service
// worker por mensagem; ele fala com a API.

import { API_BASE_URL } from "./config.js";

/** Erro de API com o status e o `detail` que o FastAPI devolve. */
export class ApiError extends Error {
  constructor(status, detail) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function get(path, { timeoutMs = 5000 } = {}) {
  // A extensão vive numa aba de terceiro: se a API não responder, é melhor desistir
  // rápido e ficar em silêncio do que segurar a UI da SERP.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = await res
        .json()
        .then((b) =>
          typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail),
        )
        .catch(() => res.statusText);
      throw new ApiError(res.status, detail);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/** `GET /categories` — categorias com ao menos um produto (cobertura). */
export function getCategories() {
  return get("/categories");
}

/**
 * `GET /search` — top-N para a busca.
 * `category` vem da detecção de cobertura e restringe o resultado ao domínio certo.
 */
export async function search(q, { category, limit } = {}) {
  const qs = new URLSearchParams({ q });
  if (category) qs.set("category", category);
  const data = await get(`/search?${qs.toString()}`);
  const results = data.results || [];
  return {
    total: data.total || 0,
    criteria: data.criteria || [],
    results: limit ? results.slice(0, limit) : results,
  };
}
