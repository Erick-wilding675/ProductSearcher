"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ComparisonTable } from "@/components/ComparisonTable/ComparisonTable";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingList } from "@/components/states/loading-list";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { Button } from "@/components/ui/button";
import { ApiError, compare } from "@/lib/api";
import type { CompareResult } from "@/lib/api";

type ErroCompare = { message: string; requestId: string | null };

function CompareContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [comparison, setComparison] = useState<CompareResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ErroCompare | null>(null);
  // "Tentar de novo" refaz só o fetch; recarregar a página inteira era exagero
  // e perdia o estado do tema aplicado antes da primeira pintura.
  const [tentativa, setTentativa] = useState(0);

  const idsParam = searchParams.get("ids");

  useEffect(() => {
    const controller = new AbortController();

    async function loadComparison() {
      if (!idsParam) {
        setLoading(false);
        return;
      }

      const ids = idsParam
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean);

      if (ids.length < 2 || ids.length > 4) {
        setError({
          message: "Selecione entre 2 e 4 produtos para comparar.",
          requestId: null,
        });
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const result = await compare(ids, controller.signal);

        setComparison(result);
      } catch (err) {
        if (controller.signal.aborted) return;

        setComparison(null);

        setError(
          err instanceof ApiError
            ? {
                message: err.detail || "Não foi possível comparar os produtos.",
                requestId: err.requestId,
              }
            : {
                message:
                  err instanceof Error ? err.message : "Não foi possível comparar os produtos.",
                requestId: null,
              }
        );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadComparison();

    return () => controller.abort();
  }, [idsParam, tentativa]);

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between gap-4">
        <Button type="button" variant="outline" onClick={() => router.push("/")}>
          Voltar para busca
        </Button>

        <ThemeToggle />
      </div>

      <header className="mb-8">
        <h1 className="text-2xl font-bold sm:text-3xl">Comparação de produtos</h1>

        <p className="mt-2 text-[var(--text-muted)]">
          Compare preços e especificações dos produtos selecionados.
        </p>
      </header>

      {loading && <LoadingList />}

      {!loading && error && (
        <ErrorState
          message={error.message}
          requestId={error.requestId}
          onRetry={() => setTentativa((n) => n + 1)}
        />
      )}

      {!loading && !error && !idsParam && (
        <EmptyState
          title="Nenhum produto selecionado"
          description="Volte para a busca e selecione entre 2 e 4 produtos para comparar."
          action={<Button onClick={() => router.push("/")}>Ir para busca</Button>}
        />
      )}

      {!loading && !error && comparison && <ComparisonTable comparison={comparison} />}
    </main>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingList />}>
      <CompareContent />
    </Suspense>
  );
}
