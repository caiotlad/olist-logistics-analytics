# Dashboard Olist Logistics

Implementei o relatório nativo em **PBIP/PBIR**, com modelo semântico em TMSL, 30 medidas e cinco páginas. Os arquivos permitem acompanhar cada mudança de filtro, consulta e visual no Git.

A base real já foi conferida no PostgreSQL. Os esquemas e as referências do projeto foram validados automaticamente. **A abertura, a renderização e a execução DAX no Power BI Desktop ainda precisam ser verificadas.** O ambiente de desenvolvimento não tinha o aplicativo, e o navegador bloqueou o download oficial. Por isso, ainda não trato o dashboard como validado nem disponibilizo um PBIX exportado.

## Abrir o projeto

Depois de executar o pipeline da raiz para gerar os quatro CSVs:

```powershell
python scripts/prepare_powerbi.py
```

O comando cria `.work/powerbi-local/OlistLogistics.pbip` com o parâmetro DataFolder apontando para os CSVs deste checkout. Ele preserva os arquivos versionados e recusa sobrescrever uma cópia local já existente. Abra o PBIP no Power BI Desktop e selecione **Atualizar**.

Para preparar em um caminho curto fora do OneDrive:

```powershell
python scripts/prepare_powerbi.py --output C:\workspace\olist-powerbi
```

Use uma pasta vazia. O projeto preparado usa o modo CSV e não precisa de credenciais de banco. Os dados detalhados continuam fora do Git; outra pessoa pode reproduzi-los baixando a base e executando o pipeline.

O [PBIP versionado](OlistLogistics.pbip) aponta para o [relatório](OlistLogistics.Report/definition.pbir) e o [modelo](OlistLogistics.SemanticModel/model.bim). Para abrir a definição versionada diretamente, configure DataFolder antes de atualizar. Seu valor padrão é um exemplo, sem caminhos pessoais gravados no Git.

## Páginas

| Página | Conteúdo |
| --- | --- |
| Entregas | Pedidos, elegíveis, atrasados, taxa, mediana e P90; comparação por UF e série mensal |
| Experiência e frete | Nota por situação da entrega, notas baixas, frete e razão frete/produtos por UF |
| Categorias | Contagens distintas, taxas e valores dos itens por categoria |
| Vendedores | Contagens distintas, taxas e valores dos itens por vendedor |
| Método e limites | Denominadores, critérios de atraso, sobreposição dos grupos e atribuição da fonte |

Mês da compra, UF de destino e status ficam sincronizados nas quatro páginas analíticas. Os gráficos de atraso e as tabelas de grupos exigem 30 elegíveis no contexto filtrado. Os cartões usam o universo do recorte; as tabelas de grupos podem omitir linhas menores que o mínimo.

Os cartões das páginas de categoria e vendedor contam pedidos distintos da ponte correspondente. A soma das linhas da tabela não representa pedidos únicos. As relações têm direção única para evitar que uma seleção em uma ponte produza efeitos inesperados na outra.

## Modelo

| Origem do filtro | Destino | Cardinalidade |
| --- | --- | --- |
| calendar[date] | fact_orders[purchase_date] | 1 para muitos |
| fact_orders[order_id] | seller_orders[order_id] | 1 para muitos |
| fact_orders[order_id] | category_orders[order_id] | 1 para muitos |

O modelo tem consultas M e medidas DAX já incluídas em `model.bim`; não é necessário criá-las manualmente. [Measures.dax](Measures.dax) é uma cópia de referência para leitura. A função [fnOlistTable.m](fnOlistTable.m) permanece como exemplo auxiliar para consultar somente o PostgreSQL.

## Usar PostgreSQL

Faça a carga real com `--with-postgres`, conforme o README da raiz. Na cópia local do projeto, abra Transformar dados > Editar parâmetros e altere SourceMode para `PostgreSQL`. Configure PostgresServer (padrão `localhost:5433`) e PostgresDatabase (padrão `olist`).

Informe as credenciais pelo conector. Não grave senhas nos arquivos do projeto. As duas origens usam os mesmos marts, os mesmos nomes de colunas e as mesmas regras.

## Validar antes de exportar

A validação dos arquivos pode ser repetida sem o Desktop:

```powershell
python -m pip install -e ".[validation]"
python scripts/validate_powerbi.py
```

O validador usa os esquemas oficiais da Microsoft, fixados em uma revisão do repositório de origem. Confere também papéis das consultas, referências dos campos, relações e limites do canvas. Isso não executa M ou DAX nem confirma a aparência dos visuais.

No Desktop, atualize a cópia local e execute [DAXQueries/Conferencia.dax](OlistLogistics.SemanticModel/DAXQueries/Conferencia.dax) na exibição de consultas DAX. Sem filtros, o resultado deve ser:

| Medida | Valor esperado |
| --- | ---: |
| Pedidos | 99.441 |
| Entregas elegíveis | 96.470 |
| Entregas atrasadas | 6.534 |
| Taxa de atraso | 0,06773090079817559 |
| Mediana de entrega | 10,217476851851853 |
| P90 de entrega | 23,09637731481482 |
| Frete registrado | R$ 2.251.909,54 |
| Valor dos produtos | R$ 13.591.643,70 |
| Entregues sem data válida | 8 |

Confira também os filtros por UF: SP tem 40.494 elegíveis e 1.820 atrasos; RJ tem 12.350 e 1.495; AL tem 397 e 85. As notas médias são 4,2903860559 no prazo e 2,2704905187 com atraso.

Teste os três filtros sincronizados, a ocultação de grupos pequenos, os estados sem elegíveis e a seleção de linhas nas pontes. Confira que nada corta nos cartões e que a escala de notas vai de 0 a 5.

Depois dessa conferência, use Arquivo > Salvar como para exportar `OlistLogistics.pbix`. O PBIP permanece como fonte versionada.

## Referências técnicas

- [Projetos Power BI Desktop](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- [Relatórios PBIR](https://learn.microsoft.com/power-bi/developer/projects/projects-report)
- [Modelo semântico do projeto](https://learn.microsoft.com/power-bi/developer/projects/projects-dataset)
- [Esquemas oficiais](https://github.com/microsoft/json-schemas)
