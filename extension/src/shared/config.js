// Configuração da extensão.
//
// `API_BASE_URL` precisa constar em `host_permissions` no manifest — trocar aqui
// sem trocar lá faz toda requisição falhar por permissão.

export const API_BASE_URL = "http://localhost:8000";

/** Web app, para o link "ver todos" (RF-54). */
export const WEB_APP_URL = "http://localhost:3000";

/** Quantos produtos o popup e o painel da SERP mostram. */
export const TOP_N = 3;

/**
 * Validade do cache de cobertura de categorias. As categorias cobertas mudam com a
 * ingestão do catálogo, não a cada busca — reconsultar a cada SERP seria desperdício
 * de rede e exporia a query sem necessidade.
 */
export const COVERAGE_TTL_MS = 60 * 60 * 1000; // 1 hora
