"use client";

import type { SortOption } from "@/lib/api";

type SortSelectProps = {
  value: SortOption;
  onChange: (sort: SortOption) => void;
  disabled?: boolean;
};

/**
 * Rótulos das ordenações do `GET /search?sort=`.
 * A ordem aqui é a ordem do select; `relevance` primeiro porque é o default do
 * backend e o que o ranking explicável (RF-31) justifica.
 */
const OPCOES: { value: SortOption; label: string }[] = [
  { value: "relevance", label: "Relevância" },
  { value: "price_asc", label: "Menor preço" },
  { value: "price_desc", label: "Maior preço" },
  { value: "name", label: "Nome (A–Z)" },
];

/** Trocar a ordenação reordena o mesmo pool de candidatos — não refaz o retrieval. */
export function SortSelect({ value, onChange, disabled = false }: SortSelectProps) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="sort-select" className="whitespace-nowrap text-sm font-medium">
        Ordenar por
      </label>

      <select
        id="sort-select"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as SortOption)}
        className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:opacity-60"
      >
        {OPCOES.map((opcao) => (
          <option key={opcao.value} value={opcao.value}>
            {opcao.label}
          </option>
        ))}
      </select>
    </div>
  );
}
