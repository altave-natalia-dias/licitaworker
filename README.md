# licitaworker

Buscador e monitor diário de licitações de **ar condicionado, pintura e limpeza de calhas**
publicadas no [PNCP](https://pncp.gov.br) (Portal Nacional de Contratações Públicas), com
foco no Estado de São Paulo — destacando Vale do Paraíba e ABC Paulista — e priorizando
avisos de contratação direta / dispensa, além de pregões de prefeituras, autarquias e
estatais (Sabesp, parques tecnológicos etc.).

Painel ao vivo (Artifact): https://claude.ai/code/artifact/af45da6e-799e-43af-ba3e-3ce97cb1eb7b

## O que tem aqui

- `scripts/fetch_licitacoes.py` — consulta a API pública de busca do PNCP, categoriza os
  resultados (ar condicionado / pintura / calhas), classifica a região (Vale do Paraíba /
  ABC Paulista / outras regiões de SP), marca prioridade (Dispensa / Aviso de Contratação
  Direta) e confiança do match (o termo aparece de fato no título/descrição visível ou só
  bateu em algum item interno do edital). Grava um JSON em `data/licitacoes_latest.json`.
- `scripts/dashboard.html` — o artifact publicado: dashboard com filtros por categoria,
  região, prioridade e confiança, lendo do banco (`db` capability) do artifact.

## Rodando localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests
python3 scripts/fetch_licitacoes.py
```

## Rotina automática

Uma rotina agendada (cloud agent) roda `scripts/fetch_licitacoes.py` todos os dias e
grava os resultados novos no banco do artifact via `write_db`, removendo automaticamente
oportunidades cujo prazo de proposta já encerrou.
