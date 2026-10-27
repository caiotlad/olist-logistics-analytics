# Preparação do Power BI

Quero que o dashboard use os mesmos marts e as mesmas regras do relatório. Esta pasta contém a função M, as medidas DAX e o tema. **Ainda não existe um arquivo .pbix montado e validado**; os arquivos abaixo são uma preparação para essa etapa, sem execução no Desktop.

## Obter os dados

1. Importe o ZIP e execute a carga com PostgreSQL, seguindo o README da raiz.
2. No Power BI Desktop, abra Transformar dados e crie uma consulta em branco chamada `fnOlistTable`.
3. Cole o conteúdo de [fnOlistTable.m](fnOlistTable.m) no Editor Avançado.
4. Crie quatro consultas usando as expressões abaixo e dê a cada uma o nome indicado.
5. Informe as credenciais do PostgreSQL no conector. Use o modo de importação.

| Consulta | Expressão M |
| --- | --- |
| fact_orders | `= fnOlistTable("localhost:5433", "olist", "fact_orders")` |
| seller_orders | `= fnOlistTable("localhost:5433", "olist", "seller_orders")` |
| category_orders | `= fnOlistTable("localhost:5433", "olist", "category_orders")` |
| calendar | `= fnOlistTable("localhost:5433", "olist", "calendar")` |

Ajuste servidor, porta e banco se mudar o Compose. Não coloque senha na consulta. A função consulta apenas as quatro views permitidas e aplica os tipos usados pelas medidas.

## Relacionamentos

Desative a criação automática de relações e configure somente estas:

| Origem | Destino | Cardinalidade | Filtro |
| --- | --- | --- | --- |
| calendar[date] | fact_orders[purchase_date] | 1 para muitos | Único, da calendar |
| fact_orders[order_id] | seller_orders[order_id] | 1 para muitos | Único, de fact_orders |
| fact_orders[order_id] | category_orders[order_id] | 1 para muitos | Único, de fact_orders |

Marque calendar como tabela de datas. Não crie relações diretas adicionais do calendário para as pontes, nem relações entre as pontes: isso criaria caminhos concorrentes.

Os filtros gerais de mês, UF e status devem vir de calendar ou fact_orders. Campos da ponte filtram apenas suas próprias medidas; não configure filtro bidirecional para fazer cartões gerais reagirem a vendedores ou categorias. Nas páginas desses recortes, use as medidas específicas de cada ponte e deixe esse comportamento explícito.

## Medidas e páginas

Crie as medidas de [Measures.dax](Measures.dax) uma por vez. O arquivo é uma referência para o editor de medidas, não um script DAX de consulta executável. Ajuste o separador de argumentos caso a configuração regional do Desktop exija.

Formate taxas como porcentagem com duas casas, tempos como decimal e valores financeiros como reais. Importe [theme.json](theme.json) em Exibição > Temas.

| Página | Visuais | Filtros e cuidados |
| --- | --- | --- |
| Entregas | Cartões de pedidos, elegíveis, atrasados, taxa, mediana e P90; barras por UF; série mensal | Mês de compra e UF; mostrar quantidade elegível junto às taxas |
| Experiência e frete | Nota média por delivered_late; valores de produtos e frete; proporção de frete | Filtrar delivery_eligible=true para comparar notas; frete inclui o universo de status selecionado |
| Categorias | Tabela com categoria, elegíveis, atrasados e taxa específica da categoria | Ocultar taxa para menos de 30 elegíveis; contagens não aditivas |
| Vendedores | Tabela com vendedor, elegíveis, atrasados e taxa específica do vendedor | Usar as medidas da ponte, sem atribuir causalidade ao vendedor |

Use `Taxa de atraso - mínimo 30` nas comparações gerais por grupo. A medida simples permanece nos cartões. Se aplicar filtros, o limite de 30 é recalculado no contexto selecionado.

## Conferência antes de publicar

Sem filtros, fact_orders deve ter 99.441 linhas e order_id sem duplicação. Os cartões devem mostrar 96.470 elegíveis, 6.534 atrasos, 6,7730900798% de atraso e mediana de 10,2174768519 dias.

Confira também SP: 40.494 elegíveis e 1.820 atrasos; RJ: 12.350 e 1.495; AL: 397 e 85. As taxas devem bater com `reports/tables/by_state.csv`.

A nota média por atraso deve ser 4,2903860559 para o grupo no prazo e 2,2704905187 para o atrasado. Nulos de nota devem permanecer ausentes, sem virar zero.

Cheque que os valores monetários foram divididos por 100, os relacionamentos têm direção única e o filtro de mês usa a compra. Só depois desses checks o dashboard poderá ser tratado como validado.

## Referências

- [Conector PostgreSQL do Power Query](https://learn.microsoft.com/power-query/connectors/postgresql)
- [PostgreSQL.Database](https://learn.microsoft.com/pt-br/powerquery-m/postgresql-database)
- [CALCULATE](https://learn.microsoft.com/pt-br/dax/calculate-function-dax)
