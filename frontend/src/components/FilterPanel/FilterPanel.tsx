"use client";

type FilterOption = {
  value: string;
  label: string;
};

type FilterPanelProps = {
  category: string;
  priceMax: string;
  brand: string;
  categories: FilterOption[];
  brands: FilterOption[];
  /** Categorias e marcas vêm da API (`/categories`, `/brands`) e chegam depois do 1º render. */
  loadingOptions?: boolean;
  onCategoryChange: (category: string) => void;
  onPriceMaxChange: (price: string) => void;
  onBrandChange: (brand: string) => void;
  onApply: () => void;
  onClear: () => void;
};

export function FilterPanel({
  category,
  priceMax,
  brand,
  categories,
  brands,
  loadingOptions = false,
  onCategoryChange,
  onPriceMaxChange,
  onBrandChange,
  onApply,
  onClear,
}: FilterPanelProps) {
  return (
    <aside
      aria-label="Filtros de busca"
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 md:sticky md:top-6 md:self-start"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Filtros</h2>

        <button
          type="button"
          onClick={onClear}
          className="text-sm font-medium text-[var(--primary)] hover:underline"
        >
          Limpar
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label htmlFor="filter-category" className="mb-1 block text-sm font-medium">
            Categoria
          </label>

          <select
            id="filter-category"
            value={category}
            disabled={loadingOptions}
            onChange={(event) => onCategoryChange(event.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 disabled:opacity-60"
          >
            <option value="">{loadingOptions ? "Carregando…" : "Todas"}</option>

            {categories.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filter-price" className="mb-1 block text-sm font-medium">
            Preço máximo
          </label>

          <input
            id="filter-price"
            type="number"
            min="0"
            step="0.01"
            value={priceMax}
            onChange={(event) => onPriceMaxChange(event.target.value)}
            placeholder="Ex.: 5000"
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
          />
        </div>

        <div>
          <label htmlFor="filter-brand" className="mb-1 block text-sm font-medium">
            Marca
          </label>

          <select
            id="filter-brand"
            value={brand}
            disabled={loadingOptions}
            onChange={(event) => onBrandChange(event.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 disabled:opacity-60"
          >
            <option value="">{loadingOptions ? "Carregando…" : "Todas"}</option>

            {brands.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={onApply}
          className="w-full rounded-md bg-[var(--primary)] px-4 py-2 font-medium text-[var(--primary-on)] hover:bg-[var(--primary-hover)]"
        >
          Aplicar filtros
        </button>
      </div>
    </aside>
  );
}
