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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
