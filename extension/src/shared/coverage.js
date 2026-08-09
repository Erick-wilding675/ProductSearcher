// Decide se uma busca cai em categoria coberta pelo catálogo (RF-51).
//
// Por que localmente: a extensão roda em TODA SERP do Google. Perguntar à API a cada
// busca vazaria consultas que não têm nada a ver com o produto e gastaria rede à toa.
// Então baixamos as categorias cobertas uma vez (`GET /categories`, com cache) e
// decidimos aqui — só quando há indício de cobertura a query sai do navegador.
//
// Duplicação consciente: o backend tem a mesma noção em `RuleBasedIntentParser`. Aqui é
// só um pré-filtro tolerante (erra para o lado de ativar); quem decide a categoria de
// verdade é a API. Ao acrescentar uma categoria ao catálogo, veja SINONIMOS abaixo.

/** Termos que o usuário digita mas não aparecem no nome da categoria. */
const SINONIMOS = {
  notebooks: ["notebook", "laptop", "ultrabook", "macbook"],
  headphones: ["fone", "headphone", "headset", "earbud", "airpod"],
};

/** Palavras curtas/genéricas que não identificam categoria sozinhas. */
const IRRELEVANTES = new Set([
  "de",
  "da",
  "do",
  "com",
  "para",
  "sem",
  "e",
  "ou",
]);

/** Tamanho mínimo para casar por prefixo — evita "fo" casar com "fone". */
const MIN_PREFIXO = 4;

/** "Fones de Ouvido" -> "fones de ouvido" (sem acento, minúsculo). */
export function normalizar(texto) {
  return (texto || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // remove os diacríticos separados pelo NFD
    .toLowerCase()
    .trim();
}

function tokenizar(texto) {
  return normalizar(texto)
    .split(/[^a-z0-9]+/)
    .filter((t) => t && !IRRELEVANTES.has(t));
}

/**
 * Palavras que ativam cada categoria, a partir do que a API devolve (`slug`, `name`)
 * mais os sinônimos locais. Derivar do endpoint faz uma categoria nova já funcionar
 * sem publicar a extensão de novo, desde que o nome dela seja o termo usado.
 */
export function palavrasChave(categorias) {
  const mapa = new Map();
  for (const { slug, name } of categorias || []) {
    const termos = new Set([
      ...tokenizar(slug),
      ...tokenizar(name),
      ...(SINONIMOS[slug] || []),
    ]);
    mapa.set(
      slug,
      [...termos].filter((t) => t.length >= MIN_PREFIXO),
    );
  }
  return mapa;
}

/** Casa por prefixo nos dois sentidos, para tolerar singular/plural. */
function casa(token, termo) {
  return token.startsWith(termo) || termo.startsWith(token);
}

/**
 * Categoria coberta que a busca menciona, ou `null` fora de cobertura.
 *
 * Vence o termo que aparece **primeiro** na consulta: em "fone para notebook" o
 * assunto é o fone. Mesma regra do parser do backend, para os dois não discordarem.
 */
export function categoriaDaBusca(query, categorias) {
  const tokens = tokenizar(query);
  if (!tokens.length) return null;

  const mapa = palavrasChave(categorias);
  let melhor = null;

  for (const [slug, termos] of mapa) {
    for (let i = 0; i < tokens.length; i++) {
      if (termos.some((termo) => casa(tokens[i], termo))) {
        if (melhor === null || i < melhor.posicao)
          melhor = { slug, posicao: i };
        break;
      }
    }
  }
  return melhor && melhor.slug;
}

/** Extrai a busca da URL da SERP. Só o parâmetro `q` — nada mais da página (RNF-09). */
export function queryDaSerp(url) {
  try {
    const { hostname, pathname, searchParams } = new URL(url);
    if (!/(^|\.)google\.[a-z.]+$/.test(hostname)) return null;
    if (!pathname.startsWith("/search")) return null;
    const q = (searchParams.get("q") || "").trim();
    return q || null;
  } catch {
    return null; // URL inválida (ex.: about:blank) — simplesmente não ativa
  }
}
