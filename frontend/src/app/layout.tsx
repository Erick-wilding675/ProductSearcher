import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Inter é a tipografia do design system (docs/design-system.md); `variable` alimenta
// o `fontFamily.sans` do Tailwind.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ProductSearcher",
  description: "Descoberta, comparação e análise inteligente de produtos.",
};

// Aplica o tema antes da primeira pintura: sem isso a página pisca clara antes do
// React hidratar e o toggle reler a escolha salva.
const aplicarTemaSalvo = `
(function () {
  try {
    var salvo = localStorage.getItem("theme");
    var escuro = salvo ? salvo === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList.toggle("dark", escuro);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={inter.variable} suppressHydrationWarning>
      <body className="font-sans">
        <script dangerouslySetInnerHTML={{ __html: aplicarTemaSalvo }} />
        {children}
      </body>
    </html>
  );
}
