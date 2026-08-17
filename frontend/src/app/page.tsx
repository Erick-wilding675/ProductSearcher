"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingList } from "@/components/states/loading-list";
import { FilterPanel } from "@/components/FilterPanel/FilterPanel";
import { Pagination } from "@/components/Pagination/Pagination";
import { RankPreferenceSelect } from "@/components/RankPreferenceSelect/RankPreferenceSelect";
import { ResultCard } from "@/components/ResultCard/ResultCard";
import { SearchBar } from "@/components/SearchBar/SearchBar";
import { SortSelect } from "@/components/SortSelect/SortSelect";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";

import { ApiError, getBrands, getCategories, getSpecOptions, search } from "@/lib/api";

import type {
  Brand,
  Category,
  RankByOption,
  SearchResponse,
  SortOption,
  SpecOption,
} from "@/lib/api";

const SORTS_VALIDOS: SortOption[] = ["relevance", "price_asc", "price_desc", "name"];

const RANKS_VALIDOS: RankByOption[] = ["relevance", "price", "brand", "spec"];

type ErroBusca = {
  message: string;
  requestId: string | null;
};

/** Traduz qualquer falha em mensagem + `X-Request-ID` quando a API mandou. */
function descreveErro(err: unknown, fallback: string): ErroBusca {
  if (err instanceof ApiError) {
    return {
      message: err.detail || fallback,
      requestId: err.requestId,
    };
  }

  return {
    message: err instanceof Error ? err.message : fallback,
    requestId: null,
  };
}

function formatPreferenceSpecKey(key: string): string {
  const labels: Record<string, string> = {
    gpu: "Placa de vídeo",
    ram_gb: "Memória",
    storage_gb: "Armazenamento",
    screen_in: "Tela",
    touchscreen: "Tela touchscreen",
    storage_type: "Tipo de armazenamento",
  };

  return labels[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPreferenceValue(value: string): string {
  if (value.toLowerCase() === "true") {
    return "Sim";
  }

  if (value.toLowerCase() === "false") {
    return "Não";
  }

  return value;
}

/**
 * A busca executada vive na URL.
 *
 * Isso deixa o resultado linkável e compartilhável e permite que
 * voltar/avançar do navegador restaure a busca anterior.
 */
function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // ---------------------------------------------------------------- URL

  const qUrl = searchParams.get("q") ?? "";

  const categoryUrl = searchParams.get("category") ?? "";

  const brandUrl = searchParams.get("brand") ?? "";

  const priceMaxUrl = searchParams.get("price_max") ?? "";

  const sortParam = searchParams.get("sort");

  const sortUrl: SortOption = SORTS_VALIDOS.includes(sortParam as SortOption)
    ? (sortParam as SortOption)
    : "relevance";

  const rankByParam = searchParams.get("rank_by");

  const rankByUrl: RankByOption = RANKS_VALIDOS.includes(rankByParam as RankByOption)
    ? (rankByParam as RankByOption)
    : "relevance";

  const rankBrandUrl = searchParams.get("rank_brand") ?? "";

  const rankSpecUrl = searchParams.get("rank_spec") ?? "";

  const rankSpecValueUrl = searchParams.get("rank_spec_value") ?? "";

  const pageUrl = Math.max(1, Number(searchParams.get("page")) || 1);

  const temBusca = searchParams.toString().length > 0;

  // ---------------------------------------------------------------- formulário de busca

  const [query, setQuery] = useState(qUrl);

  const [category, setCategory] = useState(categoryUrl);

  const [priceMax, setPriceMax] = useState(priceMaxUrl);

  const [brand, setBrand] = useState(brandUrl);

  useEffect(() => {
    setQuery(qUrl);
    setCategory(categoryUrl);
    setPriceMax(priceMaxUrl);
    setBrand(brandUrl);
  }, [qUrl, categoryUrl, priceMaxUrl, brandUrl]);

  // ---------------------------------------------------------------- preferência de ranking

  /*
   * Esses valores são um rascunho da interface.
   *
   * Eles não vão para a URL imediatamente porque:
   *
   * rank_by=brand sem rank_brand -> 422
   * rank_by=spec sem spec/valor  -> 422
   *
   * Então esperamos o usuário completar a escolha.
   */
  const [rankByDraft, setRankByDraft] = useState<RankByOption>(rankByUrl);

  const [rankBrandDraft, setRankBrandDraft] = useState(rankBrandUrl);

  const [rankSpecDraft, setRankSpecDraft] = useState(rankSpecUrl);

  const [rankSpecValueDraft, setRankSpecValueDraft] = useState(rankSpecValueUrl);

  useEffect(() => {
    setRankByDraft(rankByUrl);
    setRankBrandDraft(rankBrandUrl);
    setRankSpecDraft(rankSpecUrl);
    setRankSpecValueDraft(rankSpecValueUrl);
  }, [rankByUrl, rankBrandUrl, rankSpecUrl, rankSpecValueUrl]);

  // ---------------------------------------------------------------- resultados

  const [response, setResponse] = useState<SearchResponse | null>(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<ErroBusca | null>(null);

  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);

  const [tentativa, setTentativa] = useState(0);

  // ---------------------------------------------------------------- opções de catálogo

  const [categorias, setCategorias] = useState<Category[]>([]);

  const [marcas, setMarcas] = useState<Brand[]>([]);

  const [loadingOptions, setLoadingOptions] = useState(true);

  // ---------------------------------------------------------------- opções de specs

  const [specOptions, setSpecOptions] = useState<SpecOption[]>([]);

  const [loadingSpecs, setLoadingSpecs] = useState(false);

  // ---------------------------------------------------------------- URL helper

  const commit = useCallback(
    (patch: Record<string, string | number | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());

      for (const [chave, valor] of Object.entries(patch)) {
        if (valor === undefined || valor === "" || valor === 0) {
          params.delete(chave);
        } else {
          params.set(chave, String(valor));
        }
      }

      if (!("page" in patch)) {
        params.delete("page");
      }

      if (params.get("page") === "1") {
        params.delete("page");
      }

      router.push(params.toString() ? `/?${params.toString()}` : "/");
    },
    [router, searchParams]
  );

  // ---------------------------------------------------------------- executar busca/filtros

  const aplicaBusca = useCallback(() => {
    commit({
      q: query.trim() || undefined,

      category: category || undefined,

      brand: brand || undefined,

      price_max: priceMax || undefined,
    });
  }, [commit, query, category, brand, priceMax]);

  // ---------------------------------------------------------------- buscar resultados

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

        rankBy: rankByUrl,

        rankBrand: rankBrandUrl || undefined,

        rankSpec: rankSpecUrl || undefined,

        rankSpecValue: rankSpecValueUrl || undefined,

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
        if (controller.signal.aborted) {
          return;
        }

        setResponse(null);

        setError(descreveErro(err, "Não foi possível realizar a busca."));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [
    temBusca,
    qUrl,
    categoryUrl,
    brandUrl,
    priceMaxUrl,
    sortUrl,
    pageUrl,
    tentativa,
    rankByUrl,
    rankBrandUrl,
    rankSpecUrl,
    rankSpecValueUrl,
  ]);

  // ---------------------------------------------------------------- categorias e marcas

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
        if (!controller.signal.aborted) {
          setCategorias([]);
          setMarcas([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingOptions(false);
        }
      });

    return () => controller.abort();
  }, [categoryUrl]);

  // ---------------------------------------------------------------- spec-options

  useEffect(() => {
    if (rankByDraft !== "spec") {
      setSpecOptions([]);
      setLoadingSpecs(false);
      return;
    }

    const controller = new AbortController();

    setLoadingSpecs(true);

    getSpecOptions(
      {
        q: qUrl || undefined,

        category: categoryUrl || undefined,

        brand: brandUrl || undefined,

        priceMax: priceMaxUrl ? Number(priceMaxUrl) : undefined,
      },
      controller.signal
    )
      .then((resultado) => {
        setSpecOptions(resultado.specs);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setSpecOptions([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingSpecs(false);
        }
      });

    return () => controller.abort();
  }, [rankByDraft, qUrl, categoryUrl, brandUrl, priceMaxUrl]);

  // ---------------------------------------------------------------- opções formatadas

  const opcoesCategoria = useMemo(
    () =>
      categorias.map((categoryItem) => ({
        value: categoryItem.slug,

        label: `${categoryItem.name} (${categoryItem.product_count})`,
      })),
    [categorias]
  );

  const opcoesMarca = useMemo(
    () =>
      marcas.map((brandItem) => ({
        value: brandItem.slug,

        label: `${brandItem.name} (${brandItem.product_count})`,
      })),
    [marcas]
  );

  // ---------------------------------------------------------------- handlers de ranking

  function handleRankByChange(novoRank: RankByOption) {
    setRankByDraft(novoRank);
    setRankBrandDraft("");
    setRankSpecDraft("");
    setRankSpecValueDraft("");

    if (novoRank === "relevance") {
      commit({
        rank_by: undefined,
        rank_brand: undefined,
        rank_spec: undefined,
        rank_spec_value: undefined,
      });

      return;
    }

    if (novoRank === "price") {
      commit({
        rank_by: "price",
        rank_brand: undefined,
        rank_spec: undefined,
        rank_spec_value: undefined,

        // Regra da task:
        // priorizar por preço começa em menor preço.
        sort: "price_asc",
      });
    }

    /*
     * Marca e especificação ainda não são enviados.
     * Primeiro o usuário precisa completar a escolha.
     */
  }

  function handleRankBrandChange(novaMarca: string) {
    setRankBrandDraft(novaMarca);

    if (!novaMarca) {
      return;
    }

    commit({
      rank_by: "brand",
      rank_brand: novaMarca,
      rank_spec: undefined,
      rank_spec_value: undefined,

      // Marca usa a ordem do ranking.
      sort: undefined,
    });
  }

  function handleRankSpecChange(novaSpec: string) {
    setRankSpecDraft(novaSpec);

    setRankSpecValueDraft("");

    /*
     * Ainda não fazemos busca porque
     * falta escolher o valor da spec.
     */
  }

  function handleRankSpecValueChange(novoValor: string) {
    setRankSpecValueDraft(novoValor);

    if (!rankSpecDraft || novoValor === "") {
      return;
    }

    commit({
      rank_by: "spec",
      rank_brand: undefined,
      rank_spec: rankSpecDraft,
      rank_spec_value: novoValor,

      // Spec usa a ordem do ranking.
      sort: undefined,
    });
  }

  // ---------------------------------------------------------------- outros handlers

  function handleClearFilters() {
    setCategory("");
    setPriceMax("");
    setBrand("");

    commit({
      category: undefined,
      brand: undefined,
      price_max: undefined,
    });
  }

  function handleCompareChange(productId: string, selected: boolean) {
    setSelectedProducts((current) => {
      if (selected) {
        if (current.includes(productId) || current.length >= 4) {
          return current;
        }

        return [...current, productId];
      }

      return current.filter((id) => id !== productId);
    });
  }

  function handleCompare() {
    if (selectedProducts.length < 2) {
      return;
    }

    router.push(`/compare?ids=${encodeURIComponent(selectedProducts.join(","))}`);
  }

  function handlePageChange(novaPagina: number) {
    commit({
      page: novaPagina > 1 ? novaPagina : undefined,
    });

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  // ---------------------------------------------------------------- derivados

  const resultados = response?.results ?? [];

  const semResultados = temBusca && !loading && !error && resultados.length === 0;

  const rankInicial = response ? (response.page - 1) * response.page_size : 0;

  const preferenceDescription =
    rankByUrl === "brand" && rankBrandUrl
      ? `marca: ${
          marcas.find((brandItem) => brandItem.slug === rankBrandUrl)?.name ?? rankBrandUrl
        }`
      : rankByUrl === "spec" && rankSpecUrl && rankSpecValueUrl
        ? `${
            specOptions.find((spec) => spec.key === rankSpecUrl)?.label ??
            formatPreferenceSpecKey(rankSpecUrl)
          }: ${formatPreferenceValue(rankSpecValueUrl)}`
        : undefined;

  // ---------------------------------------------------------------- render

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8 pb-36 sm:pb-28">
      <div className="mb-4">
        <ThemeToggle />
      </div>

      <header className="mb-8">
        <h1 className="text-2xl font-bold sm:text-3xl">🔎 ProductSearcher</h1>

        <p className="mt-2 text-[var(--text-muted)]">Descoberta inteligente de produtos.</p>
      </header>

      <SearchBar value={query} onChange={setQuery} onSearch={aplicaBusca} />

      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        {/* Coluna lateral */}
        <div className="space-y-4 md:self-start">
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

          {temBusca && (
            <aside
              aria-label="Preferência de ranking"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
            >
              <h2 className="mb-4 text-lg font-semibold">Priorizar resultados</h2>

              <RankPreferenceSelect
                rankBy={rankByDraft}
                rankBrand={rankBrandDraft}
                rankSpec={rankSpecDraft}
                rankSpecValue={rankSpecValueDraft}
                brands={opcoesMarca}
                specs={specOptions}
                loadingBrands={loadingOptions}
                loadingSpecs={loadingSpecs}
                disabled={loading}
                onRankByChange={handleRankByChange}
                onRankBrandChange={handleRankBrandChange}
                onRankSpecChange={handleRankSpecChange}
                onRankSpecValueChange={handleRankSpecValueChange}
              />
            </aside>
          )}
        </div>

        {/* Resultados */}
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
                onChange={(sort) =>
                  commit({
                    sort: sort === "relevance" ? undefined : sort,
                  })
                }
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
                {resultados.map((product, index) => (
                  <ResultCard
                    key={product.id}
                    product={product}
                    rank={rankInicial + index + 1}
                    preferenceDescription={preferenceDescription}
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
