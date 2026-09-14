# licitaworker

Buscador e monitor diário de licitações de **ar condicionado, pintura e limpeza de calhas**
publicadas no [PNCP](https://pncp.gov.br) (Portal Nacional de Contratações Públicas), com
foco no Estado de São Paulo — destacando Vale do Paraíba e ABC Paulista — e priorizando
avisos de contratação direta / dispensa, além de pregões de prefeituras, autarquias e
estatais (Sabesp, parques tecnológicos etc.).

**Painel ao vivo (grátis, 24/7, GitHub Pages):**
https://altave-natalia-dias.github.io/licitaworker/

## O que tem aqui

- `scripts/fetch_licitacoes.py` — consulta a API pública de busca do PNCP, categoriza os
  resultados (ar condicionado / pintura / calhas), classifica a região (Vale do Paraíba /
  ABC Paulista / outras regiões de SP), marca prioridade (Dispensa / Aviso de Contratação
  Direta) e confiança do match (o termo aparece de fato no título/descrição visível ou só
  bateu em algum item interno do edital).
- `scripts/build_site_data.py` — roda o coletor, gera `docs/data/bootstrap.json` (o que o
  site consome) e calcula o diff em relação à execução anterior (novas/removidas).
- `docs/index.html` — o site estático (GitHub Pages): dashboard com filtros por categoria,
  região, prioridade e confiança.
- `.github/workflows/update.yml` — GitHub Action agendada (grátis) que roda todo dia às
  07h (horário de SP), atualiza `docs/data/bootstrap.json`, comita a mudança e — se
  houver oportunidade nova — abre/atualiza uma issue com o label `radar-diario` (o GitHub
  já notifica por e-mail).

## Rodando localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests
python3 scripts/build_site_data.py
```

## Rotina automática

GitHub Actions (gratuito) roda `scripts/build_site_data.py` todos os dias, comita
`docs/data/bootstrap.json` atualizado (o GitHub Pages já serve a versão nova
automaticamente) e abre/comenta uma issue de aviso quando surge oportunidade nova.
Pode rodar manualmente também: aba **Actions** → **Atualizar radar de licitações** →
**Run workflow**.
