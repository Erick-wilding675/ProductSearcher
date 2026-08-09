"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ComparisonTable } from "@/components/ComparisonTable/ComparisonTable";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingList } from "@/components/states/loading-list";
import { Button } from "@/components/ui/button";
import { compare } from "@/lib/api";
import type { CompareResult } from "@/lib/api";

function CompareContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [comparison, setComparison] = useState<CompareResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const idsParam = searchParams.get("ids");

  useEffect(() => {
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
        setError("Selecione entre 2 e 4 produtos para comparar.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const result = await compare(ids);

        setComparison(result);
      } catch (err) {
        setComparison(null);

        setError(err instanceof Error ? err.message : "Não foi possível comparar os produtos.");
      } finally {
        setLoading(false);
      }
    }

    loadComparison();
  }, [idsParam]);

  function handleRetry() {
    window.location.reload();
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-8">
      <div className="mb-8">
        <Button type="button" variant="outline" onClick={() => router.push("/")}>
          Voltar para busca
        </Button>
      </div>

      <header className="mb-8">
        <h1 className="text-2xl font-bold sm:text-3xl">Comparação de produtos</h1>

        <p className="mt-2 text-[var(--text-muted)]">
          Compare preços e especificações dos produtos selecionados.
        </p>
      </header>

      {loading && <LoadingList />}

      {!loading && error && <ErrorState message={error} onRetry={handleRetry} />}

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
