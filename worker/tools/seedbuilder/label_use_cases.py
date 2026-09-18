"""Rotula `use_case` no catálogo com um LLM — **offline**, na ingestão.

Passo 2 da Fase 6 (ADR-010 D2). A ideia central: a melhor aplicação de LLM neste
projeto não é responder o usuário, é **preparar o dado** para que o caminho
determinístico consiga responder. Depois deste passo, "notebook para jogos" é
atendido pelo filtro JSONB que já existe (RF-12) — **zero IA em runtime**, zero
latência, zero custo por request.

Guardas, todas exigidas pelo ADR:

- **Conjunto fechado.** Os rótulos permitidos saem de `categories.json` e entram
  no schema da resposta. Rótulo fora da lista é rejeitado por `validate_specs`
  antes de chegar ao banco (`data_type: enum_multi`).
- **Nada de inventar atributo.** O prompt recebe só nome, modelo, descrição e as
  specs que **já estão no banco**. O LLM classifica o que existe; não completa
  ficha técnica.
- **Idempotente e carimbado**, como o `enrich.py` (ADR-0009 D2): o resultado fica
  em `attributes._labeling` (data + modelo), e reexecutar só tenta o que faltou.

**Por que Groq, e por que não mais a Batch API.** A primeira versão deste arquivo
falava com a Batch API da Anthropic — metade do preço, e latência irrelevante num
passo offline. A chave que o projeto tem é da Groq, cujo plano gratuito **não
expõe** a Batch API (`not_available_for_plan`). Sem custo por token, o argumento
de preço que justificava o lote desaparece; o que sobra é o limite de 8.000
tokens por minuto, que esta versão respeita lendo os cabeçalhos `x-ratelimit-*`
da própria resposta. O que **não** mudou é a decisão do ADR: o LLM continua
offline, na ingestão, atrás do mesmo conjunto fechado. O fornecedor é detalhe de
transporte — a guarda é o schema, não a marca do modelo.

Como cada produto é gravado no ato, interromper e reexecutar continua de onde
parou — é o mesmo mecanismo da idempotência, não um modo separado.

**Atenção: rodar a ingestão do seed apaga os rótulos.** Eles vivem só no banco —
o YAML do seed não tem `use_case` —, e o upsert de `product_specs` substitui
`attributes` inteiro (`ingestion/load.py`), sem o cuidado que o `keep_if_null` tem
com `model`/`description`. Depois de qualquer carga do seed, rode este passo de
novo (é grátis no plano da Groq, ~25 min) — ou o filtro de `use_case` volta a não
casar com nada, em silêncio.

Uso:

    python -m tools.seedbuilder.label_use_cases --dry-run               # monta e mostra
    python -m tools.seedbuilder.label_use_cases --executar --limite 8   # piloto
    python -m tools.seedbuilder.label_use_cases --executar              # o catálogo todo
"""

import argparse
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from ingestion.pipeline import SEED_DIR
from ingestion.validate import read_categories, validate_specs

logger = logging.getLogger(__name__)

MODELO = "openai/gpt-oss-120b"
BASE_URL = "https://api.groq.com/openai/v1"

# Margem de tokens abaixo da qual o laço espera a janela virar. Uma ficha custa
# ~700 tokens entre entrada e saída; seguir com menos que isso na conta é pedir o
# 429 na requisição seguinte.
FOLGA_TOKENS = 1500

# Specs que descrevem o produto para o classificador. Não é a lista inteira do
# schema: `bluetooth` e `screen_in` não ajudam a decidir uso e só gastam token.
SPECS_RELEVANTES = (
    "cpu", "gpu", "ram_gb", "storage_gb", "storage_type", "weight_kg", "touchscreen",
    "type", "anc", "battery_h", "microphone", "water_resistant",
)  # fmt: skip

INSTRUCAO = """Você classifica produtos de um catálogo brasileiro por CASO DE USO.

Receberá a ficha de um produto. Devolva os rótulos, do conjunto fechado abaixo,
que descrevem para que este produto de fato serve.

Regras:
- Use SOMENTE os rótulos da lista. Nunca invente rótulo.
- Baseie-se nas specs, não no marketing do título. Um anúncio que diz "gamer"
  mas não tem GPU dedicada não é `jogos`.
- NO MÁXIMO 3 RÓTULOS. O rótulo é recomendação de compra, não inventário do que
  o produto aguenta. Quase todo notebook "pode" servir para estudo; o rótulo é
  para quem se **destaca** naquilo entre os concorrentes da mesma categoria.
- Rótulo que caberia em quase todo produto da categoria não distingue nada e por
  isso não deve ser usado neste produto.
- Nenhum rótulo é resposta válida: devolva lista vazia se a ficha não sustentar
  nenhum.
- Não deduza spec ausente. Se não há peso, não conclua nada sobre portabilidade.
"""

# O que cada rótulo significa — a *necessidade*, não um limiar numérico. O limiar
# viria do gabarito da suíte de relevância (D1) e o rotulador passaria a repetir o
# teste que deveria medi-lo: os números ficam fora daqui de propósito.
#
# Por categoria pelo mesmo motivo que o enum é por categoria (ADR-010 D2): a mesma
# palavra não quer dizer a mesma coisa nos dois catálogos — `jogos` em notebook é
# GPU, em fone é latência e microfone.
GLOSSARIO = {
    "notebooks": {
        "jogos": "roda jogos atuais com fluidez; depende de GPU dedicada"
                 " — vídeo integrado não sustenta o rótulo",
        "trabalho": "expediente inteiro de escritório: muitas abas, planilhas, videoconferência",
        "estudo": "aulas, textos e pesquisa; máquina equilibrada, sem exigir GPU",
        "edicao-video": "aguenta linha do tempo de vídeo: GPU dedicada e RAM sobrando",
        "programacao": "IDE, containers e compilação ao mesmo tempo: RAM sobrando e SSD",
        "portabilidade": "leve de carregar todo dia; compare com os outros notebooks"
                         " — a maioria fica perto de 2 kg, e essa maioria NÃO leva o rótulo",
    },
    "headphones": {
        "esporte": "fica firme no ouvido em movimento e aguenta suor e chuva",
        "chamadas": "microfone que se entende do outro lado, em ligações e reuniões",
        "viagem": "abafa o ruído de cabine ou de ônibus por horas seguidas",
        "trabalho": "uso contínuo no expediente: conforto por horas e microfone para reunião",
        "jogos": "áudio para jogar: latência baixa e microfone de comunicação",
    },
}  # fmt: skip


def rotulos_por_categoria(seed_dir: Path = SEED_DIR) -> dict[str, list[str]]:
    """Conjunto fechado de rótulos por categoria, lido do `categories.json`.

    Fonte única: o prompt, o schema da resposta e a validação leem daqui. Assim
    mexer no `categories.json` não deixa o rotulador para trás.
    """
    permitidos = {}
    for categoria in read_categories(seed_dir):
        for atributo in categoria.attributes:
            if atributo.attribute_key == "use_case":
                permitidos[categoria.slug] = list(atributo.allowed_values or [])
    return permitidos


def produtos_para_rotular(conn: sa.Connection, refazer: bool = False) -> list[dict[str, Any]]:
    """Fichas do banco. Sem `refazer`, pula quem já tem `use_case` gravado."""
    linhas = conn.execute(
        sa.text(
            "select p.id, p.name, p.model, p.description, c.slug as categoria, "
            "coalesce(ps.attributes, '{}'::jsonb) as attributes "
            "from products p "
            "join categories c on c.id = p.category_id "
            "left join product_specs ps on ps.product_id = p.id "
            "order by p.slug"
        )
    ).all()

    fichas = []
    for linha in linhas:
        atributos = linha.attributes or {}
        if not refazer and atributos.get("use_case"):
            continue
        fichas.append(
            {
                "id": str(linha.id),
                "categoria": linha.categoria,
                "name": linha.name,
                "model": linha.model,
                # A descrição do marketplace é longa e repetitiva; o começo já traz
                # o que importa e o corte segura o custo do lote.
                "description": (linha.description or "")[:1200],
                "specs": {k: v for k, v in atributos.items() if k in SPECS_RELEVANTES},
            }
        )
    return fichas


def _glossario(ficha: dict[str, Any], permitidos: list[str]) -> str:
    """Os rótulos da categoria, um por linha, com a necessidade que cada um nomeia.

    A lista de rótulos continua vindo do `categories.json`; o glossário só explica
    os que existem. Rótulo novo no seed sem verbete aqui entra assim mesmo — sem
    explicação, mas nunca sem estar na lista.
    """
    glosas = GLOSSARIO.get(ficha["categoria"], {})
    return "\n".join(
        f"- `{rotulo}`: {glosas[rotulo]}" if rotulo in glosas else f"- `{rotulo}`"
        for rotulo in permitidos
    )


def monta_requisicao(ficha: dict[str, Any], permitidos: list[str]) -> dict[str, Any]:
    """Os argumentos de uma chamada — uma ficha por requisição, resposta por chave."""
    corpo = {
        "nome": ficha["name"],
        "modelo": ficha["model"],
        "descricao": ficha["description"],
        "specs": ficha["specs"],
    }
    return {
        "model": MODELO,
        "temperature": 0,
        # Classificar com regra escrita não pede cadeia longa de raciocínio, e o
        # token de raciocínio conta no limite por minuto como qualquer outro.
        "reasoning_effort": "low",
        "messages": [
            {
                "role": "system",
                "content": INSTRUCAO + "\nRótulos permitidos:\n" + _glossario(ficha, permitidos),
            },
            {"role": "user", "content": json.dumps(corpo, ensure_ascii=False, indent=2)},
        ],
        # O schema fecha o conjunto no próprio contrato da resposta: o modelo não
        # tem por onde devolver rótulo fora da lista. `validate_specs` continua
        # conferindo — schema é a primeira guarda, não a única.
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "use_case",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "use_case": {
                            "type": "array",
                            "items": {"type": "string", "enum": permitidos},
                        }
                    },
                    "required": ["use_case"],
                    "additionalProperties": False,
                },
            },
        },
    }


def _cliente():
    """Importa o SDK só quando vai usar — `--dry-run` roda sem a dependência."""
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise SystemExit(
            "SDK ausente. Instale com: pip install -e .[ai]\n"
            "(fica em dependência opcional: a ingestão não precisa dele)"
        ) from exc
    chave = os.environ.get("GROQ_API_KEY")
    if not chave:
        raise SystemExit("Defina GROQ_API_KEY no worker/.env ou no ambiente.")
    # `max_retries` cobre o 429 que escapar do controle de folga abaixo: o SDK
    # respeita o `retry-after` que a Groq devolve.
    return OpenAI(api_key=chave, base_url=BASE_URL, max_retries=5, timeout=60.0)


def _segundos(valor: str | None) -> float:
    """`"2.06s"`, `"1m26.4s"` → segundos. É o formato do reset nos cabeçalhos."""
    if not valor:
        return 0.0
    total, numero = 0.0, ""
    for char in valor:
        if char.isdigit() or char == ".":
            numero += char
        elif char == "m":
            total, numero = total + float(numero or 0) * 60, ""
        elif char == "s":
            total, numero = total + float(numero or 0), ""
    return total + float(numero or 0)


def classifica(cliente, requisicao: dict[str, Any]) -> tuple[list[str] | None, float]:
    """Rótulos de um produto, e quantos segundos esperar antes do próximo.

    A espera sai dos cabeçalhos da própria resposta (`x-ratelimit-remaining-tokens`,
    `x-ratelimit-reset-tokens`): quem dita o ritmo é o servidor, não um número
    chutado aqui. Resposta ilegível devolve `None` — o produto fica sem rótulo e a
    execução segue, que é a política "rejeita, loga e segue" do ADR-0005 D6.
    """
    bruta = cliente.chat.completions.with_raw_response.create(**requisicao)
    resposta = bruta.parse()

    espera = 0.0
    restantes = bruta.headers.get("x-ratelimit-remaining-tokens")
    if restantes is not None and float(restantes) < FOLGA_TOKENS:
        espera = _segundos(bruta.headers.get("x-ratelimit-reset-tokens"))

    texto = resposta.choices[0].message.content or ""
    try:
        return json.loads(texto)["use_case"], espera
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("resposta ilegível (%.80s)", texto)
        return None, espera


def grava(conn: sa.Connection, produto_id: str, valores: list[str], schema) -> str:
    """Escreve os rótulos de um produto, se passarem em `validate_specs`.

    A gravação é por produto e no ato: o catálogo inteiro leva dezenas de minutos
    contra o limite por minuto, e perder tudo por uma queda de rede no fim seria o
    oposto da idempotência que este passo promete.
    """
    if not valores:
        return "vazios"
    # Só o spec de `use_case`, não o schema inteiro: `validate_specs` também cobra
    # os atributos `required` da categoria, e aqui a ficha é **parcial** — uma
    # atualização de um único atributo. Com o schema completo, todo fone era
    # rejeitado por "atributo obrigatório ausente: type" e o rótulo nunca chegava
    # ao banco. A guarda que importa (conjunto fechado) continua sendo aplicada.
    erros = validate_specs(
        {"use_case": valores}, [s for s in schema if s.attribute_key == "use_case"]
    )
    if erros:
        logger.warning("Produto %s rejeitado: %s", produto_id, "; ".join(erros))
        return "rejeitados"

    carimbo = {
        "use_case": valores,
        "_labeling": {"data": str(date.today()), "modelo": MODELO},
    }
    conn.execute(
        sa.text(
            "update product_specs set attributes = attributes || cast(:novo as jsonb) "
            "where product_id::text = :id"
        ),
        {"novo": json.dumps(carimbo), "id": produto_id},
    )
    return "gravados"


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="monta o lote e mostra, não envia")
    parser.add_argument("--executar", action="store_true", help="rotula e grava")
    parser.add_argument("--limite", type=int, help="para depois de N produtos (piloto)")
    parser.add_argument("--refazer", action="store_true", help="rotula também quem já tem rótulo")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL.")
    # `prepare_threshold=None` pelo mesmo motivo já documentado em
    # `api/app/core/db.py`: o Supabase é acessado pelo pooler em modo transação
    # (6543), que multiplexa sessões, e prepared statement é por sessão. As outras
    # ferramentas do worker escapam por abrirem **uma** transação; esta grava
    # produto a produto e reencontra o `_pg3_0` de outra sessão na segunda escrita
    # — foi exatamente onde a primeira execução morreu, depois de 7 produtos.
    #
    # `pool_pre_ping` + `pool_recycle`: este laço passa a maior parte do tempo
    # **dormindo** — até 50 s por vez, esperando a janela de tokens da Groq virar.
    # Nesse intervalo o pooler do Supabase fecha a conexão ociosa, e a iteração
    # seguinte pega do pool um socket morto: "server closed the connection
    # unexpectedly", já no meio da execução (aconteceu no produto 182 de 235). O
    # ping descarta a conexão morta e abre outra; o recycle evita chegar nesse
    # ponto na maioria das vezes.
    engine = sa.create_engine(
        url,
        future=True,
        connect_args={"prepare_threshold": None},
        pool_pre_ping=True,
        pool_recycle=300,
    )

    categorias = read_categories(SEED_DIR)
    schemas = {c.slug: c.attributes for c in categorias}

    permitidos = rotulos_por_categoria()
    with engine.connect() as conn:
        fichas = produtos_para_rotular(conn, refazer=args.refazer)
    fichas = [f for f in fichas if f["categoria"] in permitidos]
    if args.limite:
        fichas = fichas[: args.limite]

    print(f"{len(fichas)} produtos a rotular (modelo {MODELO})")
    for slug, lista in permitidos.items():
        print(f"   {slug}: {', '.join(lista)}")

    if not fichas:
        print("\nNada a fazer — todos já têm rótulo. Use --refazer para refazer.")
        return

    if not args.executar:
        exemplo = monta_requisicao(fichas[0], permitidos[fichas[0]["categoria"]])
        print(f"\n(dry-run — nada enviado)\nExemplo de ficha enviada ({fichas[0]['id']}):")
        print(exemplo["messages"][1]["content"][:700])
        return

    cliente = _cliente()
    contagens = {"gravados": 0, "rejeitados": 0, "vazios": 0, "ilegiveis": 0}
    for indice, ficha in enumerate(fichas, start=1):
        requisicao = monta_requisicao(ficha, permitidos[ficha["categoria"]])
        valores, espera = classifica(cliente, requisicao)
        if valores is None:
            contagens["ilegiveis"] += 1
        else:
            with engine.begin() as conn:
                estado = grava(conn, ficha["id"], valores, schemas[ficha["categoria"]])
            contagens[estado] += 1
            print(f"[{indice}/{len(fichas)}] {ficha['name'][:52]:<52} {valores}", flush=True)
        if espera:
            print(f"    (limite por minuto: aguardando {espera:.0f}s)", flush=True)
            time.sleep(espera)

    print("\nresultado:", contagens)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
