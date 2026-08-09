"use client";

type PaginationProps = {
  /** Página atual, 1-based (mesma convenção do `SearchResponse.page`). */
  page: number;
  pageSize: number;
  /** `SearchResponse.total` — candidatos do pool, não o catálogo inteiro. */
  total: number;
  onPageChange: (page: number) => void;
};

/** Quantos números mostrar de cada lado da página atual antes de reticenciar. */
const JANELA = 1;

/**
 * Monta a lista de páginas com elipse: 1 … 4 [5] 6 … 12.
 * Sempre inclui a primeira e a última para dar noção de tamanho.
 */
function paginasVisiveis(page: number, totalPages: number): (number | "…")[] {
  const numeros = new Set<number>([1, totalPages]);
  for (let p = page - JANELA; p <= page + JANELA; p += 1) {
    if (p >= 1 && p <= totalPages) numeros.add(p);
  }

  const ordenadas = [...numeros].sort((a, b) => a - b);
  const saida: (number | "…")[] = [];
  let anterior = 0;

  for (const n of ordenadas) {
    if (anterior && n - anterior > 1) saida.push("…");
    saida.push(n);
    anterior = n;
  }

  return saida;
}

/**
 * Paginação numerada do resultado de busca (RF-10).
 *
 * Só renderiza quando há mais de uma página — com 1 página a barra é ruído.
 * O estado real vive na URL (`?page=`); este componente só avisa a mudança.
 */
export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const primeiro = (page - 1) * pageSize + 1;
  const ultimo = Math.min(page * pageSize, total);

  const botao =
    "min-w-9 rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium " +
    "hover:bg-[var(--surface-alt)] disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <nav
      aria-label="Paginação dos resultados"
      className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-between"
    >
      {/* aria-live: o leitor de tela anuncia o novo intervalo ao trocar de página. */}
      <p aria-live="polite" className="text-sm text-[var(--text-muted)]">
        Mostrando {primeiro}–{ultimo} de {total}
      </p>

      <ul className="flex flex-wrap items-center gap-2">
        <li>
          <button
            type="button"
            className={botao}
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            Anterior
          </button>
        </li>

        {paginasVisiveis(page, totalPages).map((item, index) =>
          item === "…" ? (
            <li
              key={`elipse-${index}`}
              aria-hidden="true"
              className="px-1 text-[var(--text-muted)]"
            >
              …
            </li>
          ) : (
            <li key={item}>
              <button
                type="button"
                onClick={() => onPageChange(item)}
                aria-label={`Página ${item}`}
                aria-current={item === page ? "page" : undefined}
                className={
                  item === page
                    ? "min-w-9 rounded-md border border-[var(--primary)] bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-on)]"
                    : botao
                }
              >
                {item}
              </button>
            </li>
          )
        )}

        <li>
          <button
            type="button"
            className={botao}
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            Próxima
          </button>
        </li>
      </ul>
    </nav>
  );
}
