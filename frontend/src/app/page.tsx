"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { LoadingList } from "@/components/states/loading-list";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { FilterPanel } from "@/components/FilterPanel/FilterPanel";
import { ResultCard } from "@/components/ResultCard/ResultCard";
import { SearchBar } from "@/components/SearchBar/SearchBar";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { search } from "@/lib/api";
import type { SearchResultItem } from "@/lib/api";

function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // `?q=` pré-preenche a busca (link "ver no ProductSearcher" da extensão, RF-54).
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [category, setCategory] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [brand, setBrand] = useState("");

  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [searched, setSearched] = useState(false);

  async function handleSearch() {
    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const response = await search({
        q: query || undefined,
        category: category || undefined,
        priceMax: priceMax ? Number(priceMax) : undefined,
        brand: brand || undefined,
      });

      setResults(response.results);
      setSelectedProducts([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível realizar a busca.",
      );
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (searchParams.get("q")) {
      handleSearch();
    }
    // Roda só na entrada vinda da extensão; buscas seguintes usam handleSearch direto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleClearFilters() {
    setCategory("");
    setPriceMax("");
    setBrand("");
  }

  function handleCompareChange(productId: string, selected: boolean) {
    setSelectedProducts((current) => {
      
      if (selected) {
        if (current.includes(productId)) {
          return current;
        }

        if (current.length >= 4) {
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

    const ids = selectedProducts.join(",");
    router.push(`/compare?ids=${encodeURIComponent(ids)}`);
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8 pb-36 sm:pb-28">      
      <ThemeToggle />

      <header className="mb-8">
        <h1 className="text-2xl font-bold sm:text-3xl">
          🔎 ProductSearcher
        </h1>
        

        <p className="mt-2 text-[var(--text-muted)]">
          Descoberta inteligente de produtos.
        </p>
      </header>

      <SearchBar
        value={query}
        onChange={setQuery}
        onSearch={handleSearch}
      />

      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <FilterPanel
          category={category}
          priceMax={priceMax}
          brand={brand}
          categories={[
            { value: "notebooks", label: "Notebooks" },
            { value: "headphones", label: "Fones de ouvido" },
          ]}
          brands={[
            { value: "lenovo", label: "Lenovo" },
            { value: "acer", label: "Acer" },
            { value: "dell", label: "Dell" },
            { value: "asus", label: "Asus" },
            { value: "jbl", label: "JBL" },
            { value: "samsung", label: "Samsung" },
            { value: "edifier", label: "Edifier" },
            { value: "logitech", label: "Logitech" },
          ]}
          onCategoryChange={setCategory}
          onPriceMaxChange={setPriceMax}
          onBrandChange={setBrand}
          onApply={handleSearch}
          onClear={handleClearFilters}
        />

        <section aria-label="Resultados da busca">
          {loading && <LoadingList />}

          {error && (
            <ErrorState
              message={error}
              onRetry={handleSearch}
            />
          )}

          {!loading && !error && results.length === 0 && (
            <EmptyState
              title={searched ? "Nenhum resultado encontrado" : "Comece uma busca"}
              description={
                searched
                  ? "Tente outros termos ou limpe os filtros."
                  : "Busque por produtos para ver os resultados aqui."
              }
            />
          )}

          <div className="space-y-4">
            {results.map((product) => (
              <ResultCard
                key={product.id}
                product={product}
                selectedForComparison={selectedProducts.includes(product.id)}
                onCompareChange={(selected) =>
                  handleCompareChange(product.id, selected)
                }
              />
            ))}
          </div>
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