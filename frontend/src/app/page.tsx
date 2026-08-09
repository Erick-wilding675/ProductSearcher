"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { LoadingList } from "@/components/states/loading-list";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { FilterPanel } from "@/components/FilterPanel/FilterPanel";
import { Pagination } from "@/components/Pagination/Pagination";
import { ResultCard } from "@/components/ResultCard/ResultCard";
import { SearchBar } from "@/components/SearchBar/SearchBar";
import { SortSelect } from "@/components/SortSelect/SortSelect";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { ApiError, getBrands, getCategories, search } from "@/lib/api";
import type { Brand, Category, SearchResponse, SortOption } from "@/lib/api";

const SORTS_VALIDOS: SortOption[] = ["relevance", "price_asc", "price_desc", "name"];

type ErroBusca = { message: string; requestId: string | null };

/** Traduz qualquer falha em mensagem + `X-Request-ID` (quando a API mandou). */
function descreveErro(err: unknown, fallback: string): ErroBusca {
  if (err instanceof ApiError) {
    return { message: err.detail || fallback, requestId: err.requestId };
  }
  return {
    message: err instanceof Error ? err.message : fallback,
    requestId: null,
  };
}

/**
 * A busca executada vive na URL (`?q=&category=&brand=&price_max=&sort=&page=`).
 *
 * Isso deixa o resultado linkável e compartilhável, faz o voltar/avançar do
 * navegador funcionar de graça e dá um só lugar de verdade para o estado — os
 * campos do formulário são rascunho até o usuário confirmar.
 */
function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // ---- estado executado (URL) ----
  const qUrl = searchParams.get("q") ?? "";
  const categoryUrl = searchParams.get("category") ?? "";
  const brandUrl = searchParams.get("brand") ?? "";
  const priceMaxUrl = searchParams.get("price_max") ?? "";
  const sortParam = searchParams.get("sort");
  const sortUrl: SortOption = SORTS_VALIDOS.includes(sortParam as SortOption)
    ? (sortParam as SortOption)
    : "relevance";
  const pageUrl = Math.max(1, Number(searchParams.get("page")) || 1);

  // Sem nenhum parâmetro é a primeira visita: nada a buscar ainda.
  const temBusca = searchParams.toString().length > 0;

  // ---- rascunho do formulário (só vira URL ao confirmar) ----
  const [query, setQuery] = useState(qUrl);
  const [category, setCategory] = useState(categoryUrl);
  const [priceMax, setPriceMax] = useState(priceMaxUrl);
  const [brand, setBrand] = useState(brandUrl);

  // Ressincroniza o formulário quando a URL muda por fora (voltar/avançar, link colado).
  useEffect(() => {
    setQuery(qUrl);
    setCategory(categoryUrl);
    setPriceMax(priceMaxUrl);
    setBrand(brandUrl);
  }, [qUrl, categoryUrl, priceMaxUrl, brandUrl]);

  // ---- resultados ----
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErroBusca | null>(null);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  // Incrementado pelo "Tentar de novo": refaz o fetch mesmo com a URL inalterada
  // (um `router.push` para a mesma URL não dispararia o efeito).
  const [tentativa, setTentativa] = useState(0);

  // ---- opções de filtro (vêm do catálogo, não de lista fixa) ----
  const [categorias, setCategorias] = useState<Category[]>([]);
  const [marcas, setMarcas] = useState<Brand[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);

  /** Reescreve a querystring preservando o resto. `page` volta a 1 salvo quando é ela que muda. */
  const commit = useCallback(
    (patch: Record<string, string | number | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());

      for (const [chave, valor] of Object.entries(patch)) {
        if (valor === undefined || valor === "" || valor === 0) params.delete(chave);
        else params.set(chave, String(valor));
      }
      if (!("page" in patch)) params.delete("page");
      if (params.get("page") === "1") params.delete("page");

      router.push(params.toString() ? `/?${params.toString()}` : "/");
    },
    [router, searchParams]
  );

  const aplicaBusca = useCallback(() => {
    commit({
      q: query.trim() || undefined,
      category: category || undefined,
      brand: brand || undefined,
      price_max: priceMax || undefined,
    });
  }, [commit, query, category, brand, priceMax]);

  // Busca sempre que a URL muda. O AbortController descarta a resposta de uma
  // busca que já não é a atual (clique rápido em páginas seguidas).
  useEffect(() => {
    if (!temBusca) {
      setResponse(null);
      setError(null);
      return;
    }

    const controller = new AbortController();

    setLoading(true);
    setError(null);

    search(
      {
        q: qUrl || undefined,
        category: categoryUrl || undefined,
        brand: brandUrl || undefined,
        priceMax: priceMaxUrl ? Number(priceMaxUrl) : undefined,
        sort: sortUrl,
        page: pageUrl,
      },
      controller.signal
    )
      .then((resultado) => {
        setResponse(resultado);
        setSelectedProducts([]);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setResponse(null);
        setError(descreveErro(err, "Não foi possível realizar a busca."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [temBusca, qUrl, categoryUrl, brandUrl, priceMaxUrl, sortUrl, pageUrl, tentativa]);

  // Categorias e marcas do catálogo. As marcas seguem a categoria filtrada para
  // não oferecer marca de notebook em uma busca de fones.
  useEffect(() => {
    const controller = new AbortController();

    setLoadingOptions(true);
    Promise.all([
      getCategories(controller.signal),
      getBrands(categoryUrl || undefined, controller.signal),
    ])
      .then(([cats, brs]) => {
        setCategorias(cats);
        setMarcas(brs);
      })
      .catch(() => {
        // Falha aqui degrada o filtro, não a busca: os selects ficam só com "Todas".
        if (!controller.signal.aborted) {
          setCategorias([]);
          setMarcas([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingOptions(false);
      });

    return () => controller.abort();
  }, [categoryUrl]);

  const opcoesCategoria = useMemo(
    () => categorias.map((c) => ({ value: c.slug, label: `${c.name} (${c.product_count})` })),
    [categorias]
  );
  const opcoesMarca = useMemo(
    () => marcas.map((b) => ({ value: b.slug, label: `${b.name} (${b.product_count})` })),
    [marcas]
  );

  function handleClearFilters() {
    setCategory("");
    setPriceMax("");
    setBrand("");
    commit({ category: undefined, brand: undefined, price_max: undefined });
  }

  function handleCompareChange(productId: string, selected: boolean) {
    setSelectedProducts((current) => {
      if (selected) {
        if (current.includes(productId) || current.length >= 4) return current;
        return [...current, productId];
      }
      return current.filter((id) => id !== productId);
    });
  }

  function handleCompare() {
    if (selectedProducts.length < 2) return;
    router.push(`/compare?ids=${encodeURIComponent(selectedProducts.join(","))}`);
  }

  function handlePageChange(novaPagina: number) {
    commit({ page: novaPagina > 1 ? novaPagina : undefined });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const resultados = response?.results ?? [];
  const semResultados = temBusca && !loading && !error && resultados.length === 0;

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8 pb-36 sm:pb-28">
      <ThemeToggle />

      <header className="mb-8">
        <h1 className="text-2xl font-bold sm:text-3xl">🔎 ProductSearcher</h1>

        <p className="mt-2 text-[var(--text-muted)]">Descoberta inteligente de produtos.</p>
      </header>

      <SearchBar value={query} onChange={setQuery} onSearch={aplicaBusca} />

      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <FilterPanel
          category={category}
          priceMax={priceMax}
          brand={brand}
          categories={opcoesCategoria}
          brands={opcoesMarca}
          loadingOptions={loadingOptions}
          onCategoryChange={setCategory}
          onPriceMaxChange={setPriceMax}
          onBrandChange={setBrand}
          onApply={aplicaBusca}
          onClear={handleClearFilters}
        />

        <section aria-label="Resultados da busca">
          {temBusca && (
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-[var(--text-muted)]">
                {loading
                  ? "Buscando…"
                  : response
                    ? `${response.total} ${response.total === 1 ? "resultado" : "resultados"}`
                    : ""}
              </p>

              <SortSelect
                value={sortUrl}
                disabled={loading}
                onChange={(sort) => commit({ sort: sort === "relevance" ? undefined : sort })}
              />
            </div>
          )}

          {loading && <LoadingList />}

          {error && (
            <ErrorState
              message={error.message}
              requestId={error.requestId}
              onRetry={() => setTentativa((n) => n + 1)}
            />
          )}

          {!loading && !error && resultados.length === 0 && (
            <EmptyState
              title={semResultados ? "Nenhum resultado encontrado" : "Comece uma busca"}
              description={
                semResultados
                  ? "Tente outros termos ou limpe os filtros."
                  : "Busque por produtos para ver os resultados aqui."
              }
            />
          )}

          {!loading && !error && resultados.length > 0 && (
            <>
              <div className="space-y-4">
                {resultados.map((product) => (
                  <ResultCard
                    key={product.id}
                    product={product}
                    selectedForComparison={selectedProducts.includes(product.id)}
                    onCompareChange={(selected) => handleCompareChange(product.id, selected)}
                  />
                ))}
              </div>

              {response && (
                <Pagination
                  page={response.page}
                  pageSize={response.page_size}
                  total={response.total}
                  onPageChange={handlePageChange}
                />
              )}
            </>
          )}

          {selectedProducts.length > 0 && (
            <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-[var(--border)] bg-[var(--surface)] shadow-lg">
              <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-medium">
                    {selectedProducts.length}{" "}
                    {selectedProducts.length === 1
                      ? "produto selecionado"
                      : "produtos selecionados"}
                  </p>

                  <p className="text-sm text-[var(--text-muted)]">
                    Selecione de 2 a 4 produtos para comparar.
                  </p>
                </div>

                <Button
                  type="button"
                  onClick={handleCompare}
                  disabled={selectedProducts.length < 2}
                  className="w-full sm:w-auto"
                >
                  Comparar produtos
                </Button>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<LoadingList />}>
      <SearchPageContent />
    </Suspense>
  );
}
