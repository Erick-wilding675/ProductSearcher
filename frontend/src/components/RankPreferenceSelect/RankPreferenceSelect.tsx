"use client";

import type { RankByOption, SpecOption } from "@/lib/api";

type PreferenceOption = {
  value: string;
  label: string;
};

type RankPreferenceSelectProps = {
  rankBy: RankByOption;
  rankBrand: string;
  rankSpec: string;
  rankSpecValue: string;

  brands: PreferenceOption[];
  specs: SpecOption[];

  loadingBrands?: boolean;
  loadingSpecs?: boolean;
  disabled?: boolean;

  onRankByChange: (rankBy: RankByOption) => void;
  onRankBrandChange: (brand: string) => void;
  onRankSpecChange: (spec: string) => void;
  onRankSpecValueChange: (value: string) => void;
};

const RANK_OPTIONS: {
  value: RankByOption;
  label: string;
}[] = [
  {
    value: "relevance",
    label: "Relevância",
  },
  {
    value: "price",
    label: "Preço",
  },
  {
    value: "brand",
    label: "Marca",
  },
  {
    value: "spec",
    label: "Especificação",
  },
];

function formatOptionValue(value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "Sim" : "Não";
  }

  return String(value);
}

export function RankPreferenceSelect({
  rankBy,
  rankBrand,
  rankSpec,
  rankSpecValue,
  brands,
  specs,
  loadingBrands = false,
  loadingSpecs = false,
  disabled = false,
  onRankByChange,
  onRankBrandChange,
  onRankSpecChange,
  onRankSpecValueChange,
}: RankPreferenceSelectProps) {
  const selectedSpec = specs.find((spec) => spec.key === rankSpec);

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="rank-by-select" className="mb-1 block text-sm font-medium">
          Priorizar por
        </label>

        <select
          id="rank-by-select"
          value={rankBy}
          disabled={disabled}
          onChange={(event) => onRankByChange(event.target.value as RankByOption)}
          className="w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:opacity-60"
        >
          {RANK_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {rankBy === "brand" && (
        <div>
          <label htmlFor="rank-brand-select" className="mb-1 block text-sm font-medium">
            Marca
          </label>

          <select
            id="rank-brand-select"
            value={rankBrand}
            disabled={disabled || loadingBrands}
            onChange={(event) => onRankBrandChange(event.target.value)}
            className="w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:opacity-60"
          >
            <option value="">{loadingBrands ? "Carregando…" : "Escolha uma marca"}</option>

            {brands.map((brand) => (
              <option key={brand.value} value={brand.value}>
                {brand.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {rankBy === "spec" && (
        <>
          <div>
            <label htmlFor="rank-spec-select" className="mb-1 block text-sm font-medium">
              Especificação
            </label>

            <select
              id="rank-spec-select"
              value={rankSpec}
              disabled={disabled || loadingSpecs}
              onChange={(event) => onRankSpecChange(event.target.value)}
              className="w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:opacity-60"
            >
              <option value="">{loadingSpecs ? "Carregando…" : "Escolha uma especificação"}</option>

              {specs.map((spec) => (
                <option key={spec.key} value={spec.key}>
                  {spec.label}
                </option>
              ))}
            </select>
          </div>

          {rankSpec && (
            <div>
              <label htmlFor="rank-spec-value-select" className="mb-1 block text-sm font-medium">
                Valor
              </label>

              <select
                id="rank-spec-value-select"
                value={rankSpecValue}
                disabled={disabled || loadingSpecs || !selectedSpec}
                onChange={(event) => onRankSpecValueChange(event.target.value)}
                className="w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:opacity-60"
              >
                <option value="">Escolha um valor</option>

                {selectedSpec?.values.map((option) => {
                  const value = String(option.value);

                  return (
                    <option key={value} value={value}>
                      {formatOptionValue(option.value)} ({option.count})
                    </option>
                  );
                })}
              </select>
            </div>
          )}
        </>
      )}
    </div>
  );
}
