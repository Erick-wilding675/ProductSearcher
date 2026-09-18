// Configuração da extensão.
//
// `API_BASE_URL` precisa constar em `host_permissions` no manifest — trocar aqui
// sem trocar lá faz toda requisição falhar por permissão.

// Produção por padrão (ADR-0011 D6): a extensão carregada por quem vai VER a demo não
// tem backend local nenhum. Para desenvolver, troque as duas linhas pelos endereços
// locais logo abaixo — o manifest já permite os dois.
//
//   export const API_BASE_URL = "http://localhost:8000";
//   export const WEB_APP_URL = "http://localhost:3000";

export const API_BASE_URL = "https://productsearcher-api.fly.dev";

/** Web app, para o link "ver todos" (RF-54). */
export const WEB_APP_URL = "https://productsearcher.vercel.app";

/** Quantos produtos o popup e o painel da SERP mostram. */
export const TOP_N = 3;

/**
 * Validade do cache de cobertura de categorias. As categorias cobertas mudam com a
 * ingestão do catálogo, não a cada busca — reconsultar a cada SERP seria desperdício
 * de rede e exporia a query sem necessidade.
 */
export const COVERAGE_TTL_MS = 60 * 60 * 1000; // 1 hora
