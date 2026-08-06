// Cliente tipado da API do ProductSearcher.
// Os tipos espelham os schemas Pydantic do backend — ao mexer em api/app/**/schemas.py
// (ou em search/comparison.py), atualize aqui junto. Ver docs/architecture.md.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Valor monetário. Chega como **string** ("4590.00"), não number: o backend usa
 * Decimal e o Pydantic serializa em string para não perder precisão em float.
 * Use `parsePrice`/`formatPrice` — `.toFixed()` direto quebra.
 */
export type Money = string;

// ---------------------------------------------------------------- busca

/** Item do resultado de busca (`SearchResultItem`). */
export interface SearchResultItem {
  id: string;
  slug: string;
  name: string;
  category: string;
  brand: string;
  /** Menor preço entre as ofertas; `null` quando o produto não tem oferta. */
  min_price: Money | null;
}

/** Página de resultados de `GET /search` (`SearchResponse`). */
export interface SearchResponse {
  page: number;
  page_size: number;
  /** Total de produtos que casam, antes da paginação. */
  total: number;
  results: SearchResultItem[];
}

export type SortOption = "relevance" | "price_asc" | "price_desc" | "name";

export interface SearchParams {
  q?: string;
  category?: string;
  priceMax?: number;
  brand?: string;
  /** Filtro estruturado por specs (RF-12). Ex.: `{ ram_gb: 16, anc: true }`. */
  attrs?: Record<string, unknown>;
  sort?: SortOption;
  page?: number;
}

// ---------------------------------------------------------------- catálogo

/** Categoria coberta (`CategoryOut`) — a extensão usa para ativar na SERP. */
export interface Category {
  slug: string;
  name: string;
  product_count: number;
}

/** Oferta de um produto (`OfferOut`). */
export interface Offer {
  store: string;
  price: Money;
  currency: string;
  url: string;
}

/** Detalhe do produto (`ProductDetailOut`, RF-42). */
export interface ProductDetail {
  id: string;
  slug: string;
  name: string;
  model: string | null;
  description: string | null;
  category: string;
  brand: string;
  specs: Record<string, unknown>;
  offers: Offer[];
}

// ---------------------------------------------------------------- comparação

/** Produto no cabeçalho da comparação (`CompareProductInfo`). */
export interface CompareProductInfo {
  id: string;
  name: string;
  min_price: Money | null;
}

/** Uma linha da tabela de comparação (`ComparedAttribute`). */
export interface ComparedAttribute {
  key: string;
  /** Valores na MESMA ordem de `products`; `null` quando o produto não tem o atributo. */
  values: unknown[];
  /** `true` quando nem todos os produtos têm o mesmo valor — destaque da linha. */
  differ: boolean;
}

/** Resultado de `POST /compare` (`CompareOut`, RF-20/21). */
export interface CompareResult {
  category: string;
  products: CompareProductInfo[];
  /** Id do mais barato. `null` em empate ou quando ninguém tem preço. */
  best_value_id: string | null;
  attributes: ComparedAttribute[];
}

// ---------------------------------------------------------------- erros

/** Erro de API com o status e o `detail` que o FastAPI devolve. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    /** Correlaciona com o log do backend (header `X-Request-ID`). */
    readonly requestId: string | null
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    // O FastAPI responde {"detail": ...}; em 422 `detail` é uma lista de erros.
    const detail = await res
      .json()
      .then((body) => {
        const d = (body as { detail?: unknown }).detail;
        return typeof d === "string" ? d : JSON.stringify(d);
      })
      .catch(() => res.statusText);
    throw new ApiError(res.status, detail, res.headers.get("X-Request-ID"));
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------- endpoints

/**
 * `GET /search` — busca textual (FTS PT-BR) + filtros + ordenação + paginação.
 * `signal` permite cancelar a requisição anterior em busca conforme digita.
 */
export function search(params: SearchParams, signal?: AbortSignal): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.category) qs.set("category", params.category);
  if (params.priceMax != null) qs.set("price_max", String(params.priceMax));
  if (params.brand) qs.set("brand", params.brand);
  if (params.attrs && Object.keys(params.attrs).length > 0) {
    qs.set("attrs", JSON.stringify(params.attrs));
  }
  if (params.sort) qs.set("sort", params.sort);
  if (params.page) qs.set("page", String(params.page));
  return request<SearchResponse>(`/search?${qs.toString()}`, { signal });
}

/** `GET /categories` — categorias com ao menos um produto. */
export function getCategories(signal?: AbortSignal): Promise<Category[]> {
  return request<Category[]>("/categories", { signal });
}

/** `GET /products/{id}` — detalhe com specs e ofertas. */
export function getProduct(id: string, signal?: AbortSignal): Promise<ProductDetail> {
  return request<ProductDetail>(`/products/${encodeURIComponent(id)}`, {
    signal,
  });
}

/**
 * `POST /compare` — 2 a 4 produtos da MESMA categoria.
 * A ordem de `productIds` é a ordem das colunas e dos `values` de cada atributo.
 * Categorias diferentes → 400; id inexistente → 404.
 */
export function compare(productIds: string[], signal?: AbortSignal): Promise<CompareResult> {
  return request<CompareResult>("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_ids: productIds }),
    signal,
  });
}

// ---------------------------------------------------------------- helpers

/** Converte o valor monetário para number. `null` quando não há preço. */
export function parsePrice(value: Money | null): number | null {
  if (value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Formata em BRL. `fallback` (default "—") quando não há preço. */
export function formatPrice(value: Money | null, fallback = "—"): string {
  const n = parsePrice(value);
  if (n == null) return fallback;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
