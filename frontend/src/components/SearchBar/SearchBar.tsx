"use client";

type SearchBarProps = {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
};

export function SearchBar({ value, onChange, onSearch }: SearchBarProps) {
  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return (
    <form role="search" onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
      <label htmlFor="search-input" className="sr-only">
        Buscar produtos
      </label>

      <input
        id="search-input"
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Busque por produtos..."
        className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--surface)] px-4 py-2"
      />

      <button
        type="submit"
        className="w-full rounded-md bg-[var(--primary)] px-5 py-2 font-medium text-[var(--primary-on)] hover:bg-[var(--primary-hover)] sm:w-auto"
      >
        Buscar
      </button>
    </form>
  );
}
