"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FilterPanel } from "@/components/FilterPanel/FilterPanel";
import { ResultCard } from "@/components/ResultCard/ResultCard";
import { SearchBar } from "@/components/SearchBar/SearchBar";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { search } from "@/lib/api";
import type { SearchResultItem } from "@/lib/api";

export default function HomePage() {
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
          categories={["notebooks", "headphones"]}
          brands={["Lenovo", "Acer", "Dell", "Sony"]}
          onCategoryChange={setCategory}
          onPriceMaxChange={setPriceMax}
          onBrandChange={setBrand}
          onClear={handleClearFilters}
        />

        <section aria-label="Resultados da busca">
          {loading && (
            <p role="status" className="text-[var(--text-muted)]">
              Buscando produtos...
            </p>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-md border border-red-300 bg-red-50 p-4 text-red-700"
            >
              {error}
            </p>
          )}

          {!loading && !error && results.length === 0 && (
            <p className="text-[var(--text-muted)]">
              Faça uma busca para encontrar produtos.
            </p>
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
            <p className="mt-6 text-sm text-[var(--text-muted)]">
              {selectedProducts.length} produto(s) selecionado(s) para
              comparação.
            </p>
          )}
        </section>
      </div>
    </main>
  );
}