#!/usr/bin/env python3
"""
Roda o fetch_licitacoes.py, gera docs/data/bootstrap.json (o que o site
estático em docs/index.html consome) e calcula o diff em relação à versão
anterior (novas oportunidades / oportunidades que saíram da lista), para a
GitHub Action decidir se abre/atualiza uma issue de aviso.

Uso:
    python3 scripts/build_site_data.py

Saída:
    docs/data/bootstrap.json          — snapshot atual (consumido pelo site)
    docs/data/bootstrap.previous.json — snapshot anterior (preservado p/ próxima run)
    /tmp/radar_diff.json (ou $DIFF_OUT) — resumo do diff pra Action ler
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DATA = ROOT / "docs" / "data"
CURRENT = DOCS_DATA / "bootstrap.json"
PREVIOUS = DOCS_DATA / "bootstrap.previous.json"
DIFF_OUT = Path(os.environ.get("DIFF_OUT", "/tmp/radar_diff.json"))


def slim(item: dict) -> dict:
    """Mesmo shape que o dashboard consome — mantém tudo, é só o payload."""
    return item


def main() -> None:
    # 1) roda o coletor gerando um JSON temporário completo (com metadados)
    tmp_out = ROOT / "data" / "licitacoes_latest.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "fetch_licitacoes.py"), "--out", str(tmp_out)],
        check=True,
    )
    new_payload = json.loads(tmp_out.read_text(encoding="utf-8"))
    new_payload["items"] = [slim(i) for i in new_payload["items"]]

    # 2) carrega o snapshot anterior (se existir) para diff
    old_items_by_id: dict[str, dict] = {}
    if CURRENT.exists():
        try:
            old_payload = json.loads(CURRENT.read_text(encoding="utf-8"))
            old_items_by_id = {i["id"]: i for i in old_payload.get("items", [])}
        except Exception:
            old_items_by_id = {}

    new_items_by_id = {i["id"]: i for i in new_payload["items"]}

    new_ids = set(new_items_by_id) - set(old_items_by_id)
    removed_ids = set(old_items_by_id) - set(new_items_by_id)

    novas = [new_items_by_id[i] for i in new_ids]
    novas_prioritarias = [i for i in novas if i.get("prioridade")]

    diff = {
        "total_atual": len(new_items_by_id),
        "novas": len(novas),
        "removidas": len(removed_ids),
        "novas_prioritarias": len(novas_prioritarias),
        "novas_items": sorted(novas, key=lambda i: i.get("data_publicacao") or "", reverse=True),
    }

    # 3) preserva o snapshot antigo (debug/histórico) e grava o novo
    if CURRENT.exists():
        PREVIOUS.write_text(CURRENT.read_text(encoding="utf-8"), encoding="utf-8")
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    CURRENT.write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    DIFF_OUT.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"total={diff['total_atual']} novas={diff['novas']} "
        f"removidas={diff['removidas']} novas_prioritarias={diff['novas_prioritarias']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
