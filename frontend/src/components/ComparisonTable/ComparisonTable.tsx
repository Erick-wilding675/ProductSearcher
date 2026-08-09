import type { CompareResult } from "@/lib/api";
import { formatPrice } from "@/lib/api";

type ComparisonTableProps = {
  comparison: CompareResult;
};

function formatAttributeKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatAttributeValue(value: unknown): string {
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

export function ComparisonTable({ comparison }: ComparisonTableProps) {
  const { products, best_value_id, attributes } = comparison;

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[700px] border-collapse text-left text-sm sm:text-base">
        {" "}
        <thead>
          <tr className="border-b">
            <th className="px-4 py-3 font-semibold">Especificação</th>

            {products.map((product) => (
              <th key={product.id} className="min-w-[180px] px-3 py-3 font-semibold sm:px-4">
                {product.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {/* Preço */}
          <tr className="border-b">
            <th className="min-w-[140px] px-3 py-3 font-medium sm:px-4">Preço</th>

            {products.map((product) => {
              const isBestValue = best_value_id !== null && product.id === best_value_id;

              return (
                <td
                  key={product.id}
                  className={`px-4 py-3 ${
                    isBestValue ? "bg-[var(--accent-surface)] font-bold text-[var(--success)]" : ""
                  }`}
                >
                  {formatPrice(product.min_price)}
                </td>
              );
            })}
          </tr>

          {/* Especificações */}
          {attributes.map((attribute) => (
            <tr
              key={attribute.key}
              className={`border-b ${attribute.differ ? "bg-[var(--accent-surface)]" : ""}`}
            >
              <th scope="row" className="min-w-[140px] px-3 py-3 font-medium sm:px-4">
                {formatAttributeKey(attribute.key)}
              </th>

              {products.map((product, index) => (
                <td key={product.id} className="px-3 py-3 sm:px-4">
                  {formatAttributeValue(attribute.values[index])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
