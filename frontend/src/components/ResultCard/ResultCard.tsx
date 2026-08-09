import Link from "next/link";
import type { SearchResultItem } from "@/lib/api";
import { formatPrice } from "@/lib/api";

type ResultCardProps = {
  product: SearchResultItem;
  selectedForComparison: boolean;
  onCompareChange: (selected: boolean) => void;
};

function getFactorLabel(factor: string): string {
  const labels: Record<string, string> = {
    relevance: "Relevância",
    price: "Preço",
    attributes: "Atributos",
  };

  return labels[factor] ?? factor;
}

function formatSpecKey(key: string): string {
  const labels: Record<string, string> = {
    ram_gb: "RAM",
    storage_type: "Armazenamento",
    anc: "ANC",
    driver: "Driver",
    bluetooth: "Bluetooth",
    screen: "Tela",
    battery: "Bateria",
  };

  return (
    labels[key] ??
    key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function formatSpecValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "Sim" : "Não";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  return String(value);
}

export function ResultCard({
  product,
  selectedForComparison,
  onCompareChange,
}: ResultCardProps) {
  const applicableFactors = Object.entries(product.factors).filter(
    ([, factor]) => factor.applicable,
  );

  const specs = Object.entries(product.specs);

  return (
    <article className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      {/* Cabeçalho */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm text-[var(--text-muted)]">
            {product.brand} · {product.category}
          </p>

          <h2 className="mt-1 text-lg font-semibold">
            {product.name}
          </h2>
        </div>

        <div className="shrink-0 text-right">
          {/* Badge de ranking */}
          <span className="inline-flex rounded-full bg-[var(--accent-surface)] px-3 py-1 text-sm font-semibold text-[var(--primary)]">
            Ranking: {(product.score * 100).toFixed(0)}%
          </span>

          <p className="mt-2 text-lg font-bold">
            {formatPrice(product.min_price)}
          </p>
        </div>
      </div>

      {/* Specs */}
      {specs.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {specs.map(([key, value]) => (
            <span
              key={key}
              className="rounded-full bg-[var(--surface-alt)] px-3 py-1 text-sm"
            >
              <span className="font-medium">
                {formatSpecKey(key)}:
              </span>{" "}
              {formatSpecValue(value)}
            </span>
          ))}
        </div>
      )}

      {/* Fatores do ranking */}
      {applicableFactors.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {applicableFactors.map(([key, factor]) => (
            <span
              key={key}
              className="rounded-full bg-[var(--accent-surface)] px-3 py-1 text-sm"
            >
              {getFactorLabel(key)}: {(factor.score * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      )}

      {/* Comparação */}
      <div className="mt-4 border-t border-[var(--border)] pt-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={selectedForComparison}
            onChange={(event) =>
              onCompareChange(event.target.checked)
            }
          />

          Comparar este produto
        </label>

       <Link
          href={`/products/${product.id}`}
          className="inline-flex items-center justify-center rounded-md border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--surface-alt)]"
        >
          Ver detalhes
        </Link>

      </div>
    </article>
  );
}