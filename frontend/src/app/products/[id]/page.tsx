"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingList } from "@/components/states/loading-list";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { Button } from "@/components/ui/button";
import { ApiError, formatPrice, getProduct } from "@/lib/api";
import type { ProductDetail } from "@/lib/api";

type ErroProduto = { message: string; requestId: string | null };

function formatSpecKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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

export default function ProductPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  const [product, setProduct] = useState<ProductDetail | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ErroProduto | null>(null);
  // "Tentar de novo" refaz só o fetch, em vez de recarregar a página inteira.
  const [tentativa, setTentativa] = useState(0);

  const id = params.id;

  useEffect(() => {
    const controller = new AbortController();

    async function loadProduct() {
      try {
        setLoading(true);
        setError(null);

        const result = await getProduct(id, controller.signal);

        setProduct(result);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }

        setProduct(null);

        setError(
          err instanceof ApiError
            ? {
                message: err.detail || "Não foi possível carregar o produto.",
                requestId: err.requestId,
              }
            : {
                message:
                  err instanceof Error ? err.message : "Não foi possível carregar o produto.",
                requestId: null,
              }
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    if (id) {
      loadProduct();
    } else {
      setLoading(false);
    }

    return () => {
      controller.abort();
    };
  }, [id, tentativa]);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between gap-4">
        <Button type="button" variant="outline" onClick={() => router.push("/")}>
          Voltar para busca
        </Button>

        <ThemeToggle />
      </div>

      {loading && <LoadingList />}

      {!loading && error && (
        <ErrorState
          message={error.message}
          requestId={error.requestId}
          onRetry={() => setTentativa((n) => n + 1)}
        />
      )}

      {!loading && !error && !product && (
        <EmptyState
          title="Produto não encontrado"
          description="Não foi possível encontrar os dados deste produto."
        />
      )}

      {!loading && !error && product && (
        <div className="space-y-8">
          <header>
            <div className="mb-2 flex flex-wrap gap-2 text-sm text-[var(--text-muted)]">
              <span>{product.brand}</span>
              <span aria-hidden="true">•</span>
              <span>{product.category}</span>
            </div>

            <h1 className="text-2xl font-bold sm:text-3xl">{product.name}</h1>

            {product.model && (
              <p className="mt-2 text-[var(--text-muted)]">Modelo: {product.model}</p>
            )}

            {product.description && <p className="mt-4 leading-relaxed">{product.description}</p>}
          </header>

          <section
            aria-labelledby="specifications-title"
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6"
          >
            <h2 id="specifications-title" className="mb-4 text-xl font-semibold">
              Especificações
            </h2>

            {Object.keys(product.specs).length === 0 ? (
              <p className="text-[var(--text-muted)]">Nenhuma especificação disponível.</p>
            ) : (
              <dl className="divide-y divide-[var(--border)]">
                {Object.entries(product.specs).map(([key, value]) => (
                  <div key={key} className="grid gap-1 py-3 sm:grid-cols-2">
                    <dt className="font-medium">{formatSpecKey(key)}</dt>

                    <dd className="text-[var(--text-muted)]">{formatSpecValue(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          <section
            aria-labelledby="offers-title"
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6"
          >
            <h2 id="offers-title" className="mb-4 text-xl font-semibold">
              Ofertas
            </h2>

            {product.offers.length === 0 ? (
              <p className="text-[var(--text-muted)]">Nenhuma oferta disponível no momento.</p>
            ) : (
              <div className="space-y-3">
                {product.offers.map((offer, index) => (
                  <article
                    key={`${offer.store}-${index}`}
                    className="flex flex-col gap-4 rounded-lg border border-[var(--border)] p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <h3 className="font-semibold">{offer.store}</h3>

                      <p className="mt-1 text-lg font-bold">{formatPrice(offer.price)}</p>
                    </div>

                    <a
                      href={offer.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex w-full items-center justify-center rounded-md bg-[var(--primary)] px-4 py-2 font-medium text-[var(--primary-on)] hover:bg-[var(--primary-hover)] sm:w-auto"
                    >
                      Ver oferta
                    </a>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
