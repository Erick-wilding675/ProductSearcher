import { Skeleton } from "@/components/ui/skeleton";

// Estado "carregando": esqueleto no formato da lista (melhor que spinner solto).
// role="status" + aria-live: leitor de tela anuncia "Carregando".
export function LoadingList({ count = 6 }: { count?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">Carregando resultados…</span>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex gap-4 rounded-lg border border-border bg-surface p-4">
          <Skeleton className="h-16 w-16 shrink-0" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
