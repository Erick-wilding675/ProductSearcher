// Cliente tipado da API do ProductSearcher (Fase 4).
// Consome os mesmos endpoints da extensão. Ver docs/architecture.md.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ProductHit {
  id: string;
  name: string;
  brand?: string;
  price?: number;
  specs?: Record<string, unknown>;
  rank?: number;
}

export interface SearchResult {
  items: ProductHit[];
  criteria?: string[];
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export function search(params: {
  q: string;
  category?: string;
  priceMax?: number;
  brand?: string;
  sort?: string;
  page?: number;
}): Promise<SearchResult> {
  const qs = new URLSearchParams({ q: params.q });
  if (params.category) qs.set("category", params.category);
  if (params.priceMax) qs.set("price_max", String(params.priceMax));
  if (params.brand) qs.set("brand", params.brand);
  if (params.sort) qs.set("sort", params.sort);
  if (params.page) qs.set("page", String(params.page));
  return get<SearchResult>(`/search?${qs.toString()}`);
}

export function getCategories(): Promise<{ slug: string; name: string }[]> {
  return get(`/categories`);
}

export function getProduct(id: string): Promise<ProductHit> {
  return get(`/products/${id}`);
}

export async function compare(productIds: string[]): Promise<unknown> {
  const res = await fetch(`${BASE_URL}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_ids: productIds }),
  });
  if (!res.ok) throw new Error(`API ${res.status}: /compare`);
  return res.json();
}
