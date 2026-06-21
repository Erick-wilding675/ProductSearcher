// Home / Busca — placeholder (Fase 4: SearchBar + resultados).
export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">🔎 ProductSearcher</h1>
      <p className="mt-2 text-text-muted">
        Descoberta inteligente de produtos. (Scaffold — UI da Fase 4.)
      </p>
      <button className="mt-6 rounded-md bg-primary px-4 py-2 font-semibold text-[var(--primary-on)] hover:bg-primary-hover">
        Buscar
      </button>
    </main>
  );
}
