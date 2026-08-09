"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

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

export default function HomePage() {
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [brand, setBrand] = useState("");

  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);

  async function handleSearch() {
    setLoading(true);
    setError(null);

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
    <main className="mx-auto max-w-6xl px-6 py-10">
      
      <ThemeToggle />

      <header className="mb-8">
        <h1 className="text-3xl font-bold">🔎 ProductSearcher</h1>
        

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
                title="Nenhum resultado encontrado"
                description="Faça uma busca para encontrar produtos."
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
            <div className="mt-6 flex items-center justify-between gap-4 rounded-lg border border-border bg-surface p-4">
              <p className="text-sm text-text-muted">
                {selectedProducts.length} produto(s) selecionado(s) para comparação.
              </p>

              <Button
                onClick={handleCompare}
                disabled={selectedProducts.length < 2}
              >
                Comparar produtos
              </Button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}