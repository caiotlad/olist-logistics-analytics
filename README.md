# Olist Logistics

[![CI](https://github.com/caiotlad/olist-logistics-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/caiotlad/olist-logistics-analytics/actions/workflows/ci.yml)

Criei este projeto para investigar onde se concentram os atrasos de entrega e como eles se relacionam com a experiência do cliente. Usei a base histórica da Olist para construir uma análise reproduzível, com regras explícitas para datas, valores e relacionamentos entre tabelas.

A parte de dados, o relatório HTML e um dashboard interativo em Streamlit estão implementados. O painel usa os resumos analíticos versionados e permite explorar as taxas de atraso por mês, estado e categoria, além da associação com avaliações. Veja [como abrir o dashboard](#dashboard-interativo).

## O que encontrei

Na base analisada há **99.441 pedidos**. Dos 96.478 marcados como entregues, 96.470 têm datas elegíveis para comparar prazo e entrega. Nesse grupo, **6.534 atrasaram: 6,77%**. Oito entregas ficaram fora do denominador por falta da data de entrega ao cliente.

O prazo observado mediano foi de 10,22 dias e o percentil 90 foi de 23,10 dias. Pedidos atrasados tiveram nota média de 2,27, contra 4,29 entre os entregues no prazo, considerando a última avaliação válida de cada pedido. Essa associação não permite concluir que o atraso causou a nota.

Leia a [análise dos resultados](reports/findings.md), com recortes, quantidades e limitações. O [relatório HTML](reports/analysis.html) pode ser baixado e aberto no navegador.

![Taxa de atraso por estado, com pelo menos 30 entregas elegíveis](reports/figures/late_by_state.png)

## Decisões que orientaram a solução

Escolhi o pedido como unidade principal. Itens e pagamentos são agregados separadamente antes da junção, porque juntar as linhas diretamente multiplicaria valores em pedidos com vários itens e pagamentos.

Comparei as datas de calendário para definir atraso: uma entrega na noite do dia prometido continua no prazo. Tempo de entrega em dias usa a diferença entre os timestamps. Cancelados e pedidos sem datas suficientes ficam fora do indicador de atraso.

Também mantive os valores em centavos inteiros e construí duas implementações dos indicadores gerais: pandas e SQL. A carga no PostgreSQL só é confirmada se os 19 indicadores conferirem. A divergência desfaz a transação.

As regras completas estão no [dicionário e método](docs/methodology.md).

## Executar sem banco

Requisitos: Python 3.11 ou superior. Os comandos abaixo partem da raiz deste repositório.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m olist_logistics demo
```

A demonstração usa dados sintéticos identificados como tal e gera `reports/demo/report.html`. Ela permite conhecer o fluxo sem baixar a base.

## Dashboard interativo

O painel web usa Streamlit e os resumos analíticos do projeto. Ele não precisa do Power BI nem dos CSVs brutos.

```powershell
python -m pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

O Streamlit abre o painel no navegador. Para publicar uma versão demonstrativa, aponte o deploy para `dashboard/app.py` e mantenha os arquivos agregados de `reports/` no repositório.

Para reproduzir a análise real, baixe o ZIP na [página da Olist no Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), aceite os termos da origem e coloque o arquivo na raiz do projeto:

```powershell
python -m olist_logistics import-zip archive.zip
python -m olist_logistics run
```

A importação seleciona oito CSVs conhecidos, registra SHA-256 e preserva o ZIP original. O arquivo de geolocalização não é necessário neste escopo. O relatório fica em `reports/generated/report.html`; os CSVs analíticos e o diagnóstico de qualidade ficam na mesma pasta.

O limite padrão das comparações é de 30 entregas elegíveis por grupo. Para alterá-lo, use `run --min-orders 50`. Os grupos menores continuam nos CSVs, com a coluna `meets_minimum`, e ficam fora dos gráficos comparativos.

## Executar com PostgreSQL

Com Docker Desktop em execução:

```powershell
Copy-Item .env.example .env
# Ajuste POSTGRES_PASSWORD no .env antes de subir o serviço.
docker compose up -d db
docker compose --profile tools run --rm pipeline
```

Importe o ZIP antes de executar o pipeline. A carga substitui o snapshot das oito tabelas de origem em uma transação e cria as views em `olist_mart`. A porta local padrão é 5433. A conexão usa o usuário e a senha definidos no `.env`.

No Linux, ajuste `LOCAL_UID` e `LOCAL_GID` para os resultados de `id -u` e `id -g`, para gravar os relatórios no volume com o usuário local.

Também é possível executar o Python fora do contêiner:

```powershell
python -m pip install -e ".[postgres]"
$env:DATABASE_URL = "postgresql://olist:SUA_SENHA@localhost:5433/olist"
python -m olist_logistics run --with-postgres
```

Senhas com caracteres especiais precisam de codificação adequada na URL. O serviço PostgreSQL do Compose está limitado ao endereço local.

## Organização

| Caminho | Responsabilidade |
| --- | --- |
| `src/olist_logistics/quality.py` | Contratos, chaves, datas, valores e integridade referencial |
| `src/olist_logistics/marts.py` | Pedido consolidado, pontes por vendedor/categoria e calendário |
| `src/olist_logistics/sql/` | Views e cálculo independente dos indicadores |
| `src/olist_logistics/warehouse.py` | Carga transacional e conferência SQL × pandas |
| `src/olist_logistics/report.py` | Gráficos, tabelas e relatório HTML autossuficiente |
| `reports/` | Snapshot agregado da análise real e resultados |
| `powerbi/` | Consultas M, medidas DAX, tema e roteiro de montagem |
| `tests/` | Casos de regra de negócio e integração com PostgreSQL |

## Verificação

```powershell
python -m unittest discover -s tests -v
```

São 39 testes: 37 locais e dois de integração, ativados quando `DATABASE_URL` está definido. O GitHub Actions executa todos com PostgreSQL 17, roda a demonstração completa e constrói e executa a imagem Docker. Os casos incluem multiplicação de valores em joins, entrega no próprio dia prometido, avaliações empatadas, datas impossíveis, grupos pequenos, repetição de carga e rollback por divergência.

A análise completa do ZIP passou com pandas e PostgreSQL 17. Os oito CSVs foram conferidos por SHA-256, e os 19 indicadores gerais coincidiram com o snapshot publicado. A [evidência da execução](reports/validation-postgres.json) identifica o commit e o workflow. O dashboard web lê os resumos agregados do repositório; os arquivos brutos não precisam ser publicados.

## Próximos passos

- [x] Importar e identificar a base real, conferir qualidade e relacionamentos.
- [x] Implementar os marts e os indicadores em Python e SQL.
- [x] Gerar relatório, gráficos e conclusões com denominadores explícitos.
- [x] Automatizar os testes de integração e a execução Docker.
- [x] Criar o dashboard web interativo para explorar os indicadores sem depender de uma ferramenta proprietária.
- [x] Conferir o snapshot real completo no PostgreSQL.
- [ ] Publicar uma demonstração do dashboard web para acesso pelo portfólio.

## Fonte e uso dos dados

Fonte: **Olist, Brazilian E-Commerce Public Dataset by Olist**, disponibilizada no Kaggle sob **CC BY-NC-SA 4.0**. A licença, os arquivos utilizados e a identificação do ZIP estão em [DATA_SOURCES.md](DATA_SOURCES.md).

Os resultados descrevem somente esta base histórica de 2016–2018. Não representam a operação atual da Olist. Os arquivos brutos, ZIPs e tabelas detalhadas geradas ficam fora do Git.
