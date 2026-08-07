import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">ProductSearcher</h1>
      <div className="mt-6 flex gap-3">
        <Button>Buscar</Button>
        <Button variant="outline">Comparar</Button>
      </div>
    </main>
  );
}