"""Embedding de 768 dimensões para a busca vetorial (ADR-010 D3 e D3.3).

Três invariantes do ADR são pagas **aqui**, e de propósito num lugar só:

1. **Produto e consulta têm de ser vetorizados pelo mesmo modelo.** Vetores de
   modelos diferentes vivem em espaços diferentes e a similaridade de cosseno
   entre eles não significa nada — falha silenciosa, sem erro, só resultado
   ruim. Por isso existe um único lugar onde vetor é gerado: este módulo.

2. **O `multilingual-e5-base` é assimétrico.** Ele foi treinado com os prefixos
   `query:` e `passage:`, e esquecê-los degrada o resultado *em silêncio* —
   mesma classe de falha da invariante acima. Por isso **não existe função
   pública que aceite texto cru**: quem chama pede "vetor de consulta" ou
   "vetor de produto", e o prefixo não é decisão de quem chama.

3. **Uma thread de inferência.** Medido em 22/08/2026 (ADR-010 D3.3): em 1 vCPU
   com o pool de threads no default, o p95 vai a 804 ms e fura a RNF-01 sozinho,
   antes da query SQL — o runtime dimensiona o pool pelas CPUs que *enxerga*,
   não pelas que o cgroup concede. `OMP_NUM_THREADS=1` no ambiente resolve, mas
   depende de alguém lembrar no deploy. Aqui isso é fixado **no código**, via
   `intra_op_num_threads`, para que a configuração errada não seja possível.

O runtime é ONNX Runtime com pesos quantizados em int8 (a alavanca (1) do
D3.2): mesma dimensão e mesmo modelo do fp32, com imagem de 739 MB em vez de
2546 MB e RSS de pico de 872 MB em vez de 1220 MB.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Dimensão fixada pelo ADR-0005 D2 e mantida pelo ADR-010 D3 — é a largura da
# coluna `products.embedding`, e por isso não é configurável.
DIM = 768

# Prefixos do e5. Privados: ver a invariante 2 no topo do módulo.
_PREFIXO_CONSULTA = "query: "
_PREFIXO_PRODUTO = "passage: "

# O modelo trunca em 512 tokens. Copy de marketplace raramente chega perto,
# mas truncar explicitamente é melhor que estourar dentro do runtime.
_MAX_TOKENS = 512


class DependenciaAusente(RuntimeError):
    """O extra `vector` não está instalado.

    A busca vetorial é opcional (`vector_enabled`), como toda IA neste projeto.
    Sem o extra, a API sobe e serve o FTS normalmente — o erro só aparece para
    quem tentar usar o caminho vetorial sem ter instalado o que ele precisa.
    """


class Embedder:
    """Carrega o modelo uma vez e vetoriza consultas e produtos.

    Instanciar **carrega o modelo** (~2,5 s medidos). Não instancie por request:
    use `get_embedder()`, que memoiza.
    """

    def __init__(self, model_dir: str | Path | None = None, threads: int | None = None) -> None:
        # Import tardio: sem ele, `import app.main` exigiria onnxruntime e
        # transformers mesmo com a busca vetorial desligada — o oposto do
        # princípio de que a IA é complementar.
        try:
            import numpy as np
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise DependenciaAusente(
                "Busca vetorial exige o extra `vector`: pip install './api[vector]'"
            ) from exc

        self._np = np
        self._dir = Path(model_dir or settings.embedding_model_dir)
        if not self._dir.is_dir():
            raise FileNotFoundError(
                f"Modelo de embedding não encontrado em {self._dir}. "
                "A imagem de produção o traz embutido; localmente, ver api/README-vector.md."
            )

        opcoes = ort.SessionOptions()
        # Ver invariante 3 no topo do módulo. Fixado no código, não no ambiente.
        opcoes.intra_op_num_threads = threads or settings.embedding_threads
        opcoes.inter_op_num_threads = 1

        self._tokenizer = AutoTokenizer.from_pretrained(str(self._dir))
        self._session = ort.InferenceSession(
            str(self._dir / "model_quantized.onnx"),
            opcoes,
            providers=["CPUExecutionProvider"],
        )
        # Modelos exportados variam nas entradas que aceitam (alguns não recebem
        # `token_type_ids`). Passar uma entrada que o grafo não declara é erro.
        self._entradas = {entrada.name for entrada in self._session.get_inputs()}

        # Identidade do modelo lida **dos próprios pesos** (arquivo gravado no
        # export, ver api/Dockerfile), com a config só como fallback. É o que
        # carimba os vetores dos produtos: se o carimbo viesse de uma variável
        # de ambiente, dava para trocar o modelo sem trocar o carimbo, e a
        # invariante 1 quebraria sem deixar rastro — exatamente o caso que o
        # carimbo existe para detectar.
        marcador = self._dir / "MODEL_ID"
        self.model_id = (
            marcador.read_text(encoding="utf-8").strip()
            if marcador.is_file()
            else settings.embedding_model_id
        )
        logger.info("Modelo de embedding carregado de %s (%s)", self._dir, self.model_id)

    def _encode(self, textos: Sequence[str]) -> list[list[float]]:
        """Vetoriza textos **que já vêm com o prefixo aplicado**.

        Privado de propósito: é o único caminho que aceita texto sem papel
        definido, e deixá-lo público reabriria a invariante 2.
        """
        np = self._np
        enc = self._tokenizer(
            list(textos),
            padding=True,
            truncation=True,
            max_length=_MAX_TOKENS,
            return_tensors="np",
        )
        entrada = {k: v.astype(np.int64) for k, v in enc.items() if k in self._entradas}
        ultimo_estado = self._session.run(None, entrada)[0]

        # Mean pooling mascarado + normalização L2 — é o que o
        # sentence-transformers faz para este modelo. Sem a máscara, os tokens
        # de padding entram na média e o vetor muda conforme o tamanho do lote.
        mascara = enc["attention_mask"].astype(np.float32)[..., None]
        somas = (ultimo_estado * mascara).sum(axis=1)
        vetores = somas / np.clip(mascara.sum(axis=1), 1e-9, None)
        normas = np.clip(np.linalg.norm(vetores, axis=1, keepdims=True), 1e-9, None)
        return (vetores / normas).tolist()

    def embed_query(self, texto: str) -> list[float]:
        """Vetor da consulta do usuário. Um por request, no caminho crítico."""
        return self._encode([_PREFIXO_CONSULTA + texto])[0]

    def embed_products(self, textos: Sequence[str], batch_size: int = 1) -> list[list[float]]:
        """Vetores dos produtos. Passo offline, roda uma vez por carga.

        **`batch_size=1` é o default de propósito, e custa segundos bem gastos.**

        A quantização int8 é *dinâmica*: a escala das ativações é calculada em
        tempo de execução sobre o tensor inteiro — ou seja, sobre o lote todo.
        Com isso o vetor de um produto passa a depender de **quem estava no lote
        ao lado dele**. Medido em 22/08/2026: o mesmo texto sozinho e num lote de
        dois dá cosseno 0,991 contra si mesmo; com textos de mesmo comprimento,
        sem padding nenhum, ainda dá 0,993. Não é a máscara de padding — é a
        escala da quantização.

        Sozinho, o efeito é pequeno. O problema é o que ele significa: o vetor
        gravado dependeria da ordem do catálogo e do `batch_size` da carga, então
        recarregar com outro lote mudaria os vetores sem que nada tivesse mudado
        no produto. É a mesma família de falha silenciosa que o resto deste
        módulo existe para fechar.

        Com lote de 1 o resultado é determinístico (cosseno 1,0 exato, verificado
        em teste) e independente dos vizinhos. Para ~250 produtos isso custa
        poucos segundos, uma vez. Subir o `batch_size` só se vale a pena quando o
        catálogo crescer muito — e aí é troca consciente de determinismo por
        tempo, não default.
        """
        saida: list[list[float]] = []
        for i in range(0, len(textos), batch_size):
            lote = [_PREFIXO_PRODUTO + t for t in textos[i : i + batch_size]]
            saida.extend(self._encode(lote))
        return saida


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Instância única do modelo, carregada na primeira chamada.

    Memoizada porque carregar custa ~2,5 s e ~870 MB de RSS: uma instância por
    request derrubaria o serviço. É também o que garante, na prática, que só
    exista um modelo no processo (invariante 1).
    """
    return Embedder()


def texto_do_produto(nome: str, modelo: str | None, descricao: str | None) -> str:
    """Monta o texto que representa o produto no espaço vetorial.

    Mesmos campos da coluna gerada `search_vector` (`name || model ||
    description`), e não por coincidência: os dois caminhos da busca híbrida
    (ADR-010 D4) devem enxergar o **mesmo** produto, senão a união fica
    comparando descrições diferentes do mesmo item e a diferença de resultado
    vira ruído impossível de atribuir.
    """
    partes = [nome, modelo or "", descricao or ""]
    return " ".join(parte.strip() for parte in partes if parte and parte.strip())
