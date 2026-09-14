#!/usr/bin/env python3
"""
Buscador de licitações — ar condicionado, pintura e limpeza de calhas (SP).

Consulta a API pública de busca do PNCP (Portal Nacional de Contratações
Públicas), que desde a Lei 14.133/2021 concentra a publicação obrigatória
de editais, avisos de contratação direta e dispensas de praticamente todos
os órgãos públicos do Brasil (prefeituras, governo estadual, autarquias e
empresas estatais como Sabesp).

Uso:
    python3 fetch_licitacoes.py [--out data/licitacoes_latest.json]

Saída: um JSON com a lista de oportunidades encontradas, já categorizadas,
regionalizadas (Vale do Paraíba / ABC Paulista / Outras regiões SP) e
marcadas como prioritárias quando são Dispensa ou Aviso de Contratação
Direta (conforme pedido do usuário).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://pncp.gov.br/api/search/"
PORTAL_BASE = "https://pncp.gov.br"

# Uma consulta por termo — a busca do PNCP é full-text, não booleana, então
# termos mais específicos tendem a trazer menos ruído.
CATEGORIES: dict[str, list[str]] = {
    "ar_condicionado": [
        "ar condicionado",
        "climatização",
        "manutenção de sistema de ar condicionado",
    ],
    "pintura": [
        "pintura predial",
        "pintura de fachada",
        "serviços de pintura",
    ],
    "calhas": [
        "limpeza de calhas",
        "calhas e rufos",
        "limpeza de calhas e telhado",
    ],
}

CATEGORY_LABELS = {
    "ar_condicionado": "Ar condicionado",
    "pintura": "Pintura",
    "calhas": "Limpeza de calhas",
}

# A busca do PNCP é full-text e por vezes casa com um item da planilha
# interna do edital que não aparece no título/descrição resumidos (ex.: um
# edital de "aquisição de eletrodomésticos" que tem 1 item de ar
# condicionado). Para não sujar o resultado, só marcamos "alta confiança"
# quando o próprio texto visível (título + descrição) confirma o termo.
CONFIDENCE_STEMS = {
    "ar_condicionado": [
        "ar condicionado", "ar-condicionado", "climatiza", "refrigera",
        "split", "vrf", "fancoil", "fan-coil", "fan coil", "pmoc",
    ],
    "pintura": ["pintura", "pintar", "repintura"],
    "calhas": ["calha", "rufo", "platibanda"],
}

# Municípios de interesse prioritário do usuário. Como o escopo final é o
# Estado de SP inteiro, isto serve só para etiquetar a região no dashboard,
# não para filtrar.
VALE_DO_PARAIBA = {
    "são josé dos campos", "taubaté", "jacareí", "pindamonhangaba",
    "guaratinguetá", "caçapava", "tremembé", "lorena", "cruzeiro",
    "cachoeira paulista", "aparecida", "ubatuba", "caraguatatuba",
    "são sebastião", "ilhabela", "campos do jordão", "roseira", "potim",
    "canas", "cunha", "silveiras", "areias", "bananal", "arapeí",
    "são josé do barreiro", "queluz", "lavrinhas", "piquete",
    "são luiz do paraitinga", "redenção da serra", "natividade da serra",
    "paraibuna", "santa branca", "jambeiro", "monteiro lobato", "igaratá",
}

ABC_PAULISTA = {
    "santo andré", "são bernardo do campo", "são caetano do sul",
    "diadema", "mauá", "ribeirão pires", "rio grande da serra",
}

# Padrões de nome de órgão que o usuário quer destacar (Sabesp, parques
# tecnológicos/inovação, prefeituras). Só para exibição/etiqueta.
ORG_HIGHLIGHT_PATTERNS = [
    ("sabesp", "Sabesp"),
    ("parque tecnol", "Parque Tecnológico"),
    ("parque de inova", "Parque de Inovação"),
    ("inova", "Inovação/Tech Park"),
    ("prefeitura", "Prefeitura"),
    ("municipio", "Prefeitura"),
    ("município", "Prefeitura"),
]

STATUS = "recebendo_proposta"
TIPOS_DOCUMENTO = "edital"  # inclui Edital, Aviso de Contratação Direta e
                             # Ato que autoriza a Contratação Direta (Dispensa)
UF = "SP"
PAGE_SIZE = 50
MAX_PAGES_PER_TERM = 6  # teto de segurança (até 300 resultados/termo)
REQUEST_DELAY_S = 0.6


def region_for(municipio: str | None) -> str:
    if not municipio:
        return "outras_sp"
    m = municipio.strip().lower()
    if m in VALE_DO_PARAIBA:
        return "vale_do_paraiba"
    if m in ABC_PAULISTA:
        return "abc_paulista"
    return "outras_sp"


def org_highlight(orgao_nome: str | None) -> str | None:
    if not orgao_nome:
        return None
    n = orgao_nome.lower()
    for pattern, label in ORG_HIGHLIGHT_PATTERNS:
        if pattern in n:
            return label
    return None


def is_priority(item: dict) -> bool:
    """Dispensa / Aviso de Contratação Direta — pedido explícito do usuário."""
    modalidade = (item.get("modalidade_licitacao_nome") or "").lower()
    tipo = (item.get("tipo_nome") or "").lower()
    return "dispensa" in modalidade or "contratação direta" in tipo


def fetch_term(term: str, session: requests.Session) -> list[dict]:
    results: list[dict] = []
    for page in range(1, MAX_PAGES_PER_TERM + 1):
        params = {
            "tipos_documento": TIPOS_DOCUMENTO,
            "ordenacao": "-data",
            "pagina": page,
            "tam_pagina": PAGE_SIZE,
            "q": term,
            "ufs": UF,
            "status": STATUS,
        }
        data = None
        attempts = 5
        for attempt in range(attempts):
            try:
                # PNCP às vezes derruba conexões keep-alive; força conexão nova.
                resp = requests.get(
                    API_BASE,
                    params=params,
                    timeout=20,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "buscador-licitacoes-servicos/1.0 (uso interno)",
                        "Connection": "close",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except (requests.RequestException, ValueError) as exc:
                wait = 1.5 * (attempt + 1)
                print(
                    f"  [aviso] falha na página {page} de '{term}' (tentativa {attempt + 1}/{attempts}): {exc}"
                    f" — nova tentativa em {wait:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait)
        if data is None:
            print(f"  [erro] desistindo da página {page} de '{term}' após {attempts} tentativas", file=sys.stderr)
            break

        items = data.get("items", [])
        results.extend(items)
        total = data.get("total", 0)
        if page * PAGE_SIZE >= total or not items:
            break
        time.sleep(REQUEST_DELAY_S)
    return results


def has_visible_match(categoria: str, titulo: str, descricao: str) -> bool:
    text = f"{titulo or ''} {descricao or ''}".lower()
    return any(stem in text for stem in CONFIDENCE_STEMS[categoria])


def normalize(item: dict, categoria: str) -> dict:
    numero_controle = item.get("numero_controle_pncp") or item.get("id") or ""
    doc_id = numero_controle.replace("/", "_").replace(" ", "")
    municipio = item.get("municipio_nome")
    titulo = item.get("title")
    descricao = (item.get("description") or "").strip()
    return {
        "id": doc_id,
        "numero_controle_pncp": numero_controle,
        "categoria": categoria,
        "categoria_label": CATEGORY_LABELS[categoria],
        "prioridade": is_priority(item),
        "confianca": "alta" if has_visible_match(categoria, titulo, descricao) else "baixa",
        "titulo": titulo,
        "descricao": descricao,
        "orgao": item.get("orgao_nome"),
        "orgao_destaque": org_highlight(item.get("orgao_nome")),
        "esfera": item.get("esfera_nome"),
        "poder": item.get("poder_nome"),
        "municipio": municipio,
        "uf": item.get("uf"),
        "regiao": region_for(municipio),
        "modalidade": item.get("modalidade_licitacao_nome"),
        "tipo_documento": item.get("tipo_nome"),
        "situacao": item.get("situacao_nome"),
        "valor_global": item.get("valor_global"),
        "data_publicacao": item.get("data_publicacao_pncp"),
        "data_fim_vigencia": item.get("data_fim_vigencia"),
        "link": f"{PORTAL_BASE}{item.get('item_url')}" if item.get("item_url") else None,
        "fonte": "PNCP",
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def collect() -> list[dict]:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "buscador-licitacoes-servicos/1.0 (uso interno)",
    })

    by_id: dict[str, dict] = {}
    for categoria, terms in CATEGORIES.items():
        for term in terms:
            print(f"Buscando '{term}' ({CATEGORY_LABELS[categoria]})...", file=sys.stderr)
            raw_items = fetch_term(term, session)
            print(f"  -> {len(raw_items)} resultado(s)", file=sys.stderr)
            for raw in raw_items:
                norm = normalize(raw, categoria)
                if not norm["id"]:
                    continue
                # Evita duplicar o mesmo edital encontrado por mais de um termo
                # da mesma categoria; se já existe de outra categoria, mantém
                # a primeira categoria mas registra ambas em "categorias".
                existing = by_id.get(norm["id"])
                if existing:
                    cats = set(existing.get("categorias", [existing["categoria"]]))
                    cats.add(categoria)
                    existing["categorias"] = sorted(cats)
                    if norm["confianca"] == "alta":
                        existing["confianca"] = "alta"
                else:
                    norm["categorias"] = [categoria]
                    by_id[norm["id"]] = norm
            time.sleep(REQUEST_DELAY_S)

    return list(by_id.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "licitacoes_latest.json"),
        help="Caminho do arquivo JSON de saída",
    )
    args = parser.parse_args()

    items = collect()
    items.sort(key=lambda x: x.get("data_publicacao") or "", reverse=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(items),
        "por_categoria": {
            cat: sum(1 for i in items if cat in i.get("categorias", [i["categoria"]]))
            for cat in CATEGORIES
        },
        "por_regiao": {
            reg: sum(1 for i in items if i["regiao"] == reg)
            for reg in ("vale_do_paraiba", "abc_paulista", "outras_sp")
        },
        "prioritarias": sum(1 for i in items if i["prioridade"]),
        "confianca_alta": sum(1 for i in items if i["confianca"] == "alta"),
        "items": items,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK: {len(items)} oportunidades únicas salvas em {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
