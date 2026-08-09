import type { CompareResult } from "@/lib/api";
import { formatPrice } from "@/lib/api";

type ComparisonTableProps = {
  comparison: CompareResult;
};

function formatAttributeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

export function ComparisonTable({
  comparison,
}: ComparisonTableProps) {
  const { products, best_value_id, attributes } = comparison;

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b">
            <th className="px-4 py-3 font-semibold">
              Especificação
            </th>

            {products.map((product) => (
              <th
                key={product.id}
                className="px-4 py-3 font-semibold"
              >
                {product.name}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {/* Preço */}
          <tr className="border-b">
            <th className="px-4 py-3 font-medium">
              Preço
            </th>

            {products.map((product) => {
              const isBestValue =
                best_value_id !== null &&
                product.id === best_value_id;

              return (
                <td
                  key={product.id}
                  className={`px-4 py-3 ${
                    isBestValue
                      ? "bg-[var(--accent-surface)] font-bold text-green-700"
                      : ""
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
              className={`border-b ${
                attribute.differ ? "bg-[var(--accent-surface)]" : ""
              }`}
            >
              <th
                scope="row"
                className="px-4 py-3 font-medium"
              >
                {formatAttributeKey(attribute.key)}
              </th>

              {products.map((product, index) => (
                <td
                  key={product.id}
                  className="px-4 py-3"
                >
                  {formatAttributeValue(
                    attribute.values[index],
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}