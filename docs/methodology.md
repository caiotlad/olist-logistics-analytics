# Modelo e regras dos indicadores

Meu objetivo é manter o denominador e a unidade de cada número visíveis. A base tem pedidos com vários itens, vendedores, pagamentos e avaliações; cada tabela exige um tratamento antes da análise.

## Camadas e granularidade

A importação seleciona os oito arquivos esperados do ZIP. Os dados brutos ficam em `data/raw`. O pacote verifica colunas obrigatórias, chaves, referências, datas e valores; depois produz os marts em pandas. Com `--with-postgres`, também carrega `olist_stage` e cria as views em `olist_mart`.

| Mart | Uma linha representa | Chave |
| --- | --- | --- |
| fact_orders | Um pedido, em qualquer status | order_id |
| seller_orders | A participação de um vendedor em um pedido | order_id + seller_id |
| category_orders | A presença de uma categoria em um pedido | order_id + category |
| calendar | Um dia entre a primeira e a última compra | date |

Os totais de itens e pagamentos são calculados antes de entrar no pedido. `customer_id` faz o relacionamento do pedido; `customer_unique_id` é a identidade para estudar clientes recorrentes. Não trato a contagem de `customer_id` como quantidade de pessoas.

As pontes de vendedor e categoria incluem somente pedidos com os respectivos itens. Um pedido pode aparecer em vários grupos. Por isso, a soma dos pedidos por vendedor ou categoria não é o total de pedidos. Os valores em centavos nessas pontes pertencem aos itens daquele grupo; a informação de atraso continua sendo do pedido inteiro. Ela não identifica qual vendedor ou produto causou o atraso.

## Qualidade e tratamento

- Linhas idênticas são removidas com aviso. Chaves primárias conflitantes, referências ausentes e identificadores inválidos impedem a carga.
- Datas preenchidas precisam respeitar o formato de origem. Campos ausentes são registrados, sem inventar datas.
- Valores monetários usam Decimal na validação e centavos inteiros nos marts. Valores negativos, não finitos ou frações de centavo são rejeitados.
- Frete zero e zero parcelas são permitidos. Categoria ausente vira `__unknown__`; valor monetário sem itens permanece nulo.
- Status e UF são normalizados. A ausência de data impede o indicador correspondente, sem remover o pedido do universo.
- Dados com falha estrutural geram diagnóstico e não avançam para o relatório. O manifesto guarda bytes, linhas e SHA-256.

## Prazo e atraso

Um pedido é elegível quando tem status `delivered`, compra, entrega ao cliente e promessa preenchidas; a entrega ocorre depois ou no instante da compra; o dia prometido não é anterior ao dia da compra.

| Indicador | Definição |
| --- | --- |
| Pedidos | Todas as linhas de fact_orders |
| Entregues | Status delivered |
| Elegíveis | Entregues que satisfazem a regra de datas |
| Entregues excluídos | Entregues menos elegíveis |
| Atrasados | Elegíveis cujo dia de entrega é posterior ao dia prometido |
| Taxa de atraso | Atrasados / elegíveis; nulo quando não há elegíveis |
| Tempo de entrega | (Timestamp de entrega − timestamp de compra) / 86.400 segundos |
| Mediana e P90 | Quantis 0,5 e 0,9 do tempo de entrega, com interpolação linear |
| Dias de atraso | Diferença de dias de calendário entre entrega e promessa; média só dos atrasados |

As datas da fonte não têm fuso horário. Não faço conversão para UTC. Uma promessa às 00h não significa que uma entrega às 19h do mesmo dia atrasou.

Mês é o **mês de compra**, inclusive quando a entrega ocorre depois. Uso pelo menos 30 elegíveis nos gráficos por UF, mês, vendedor ou categoria. É um filtro de tamanho de grupo, sem significância estatística implícita. Os CSVs preservam todos os grupos e informam `meets_minimum`.

Cancelados e pedidos ainda em trânsito não entram no atraso de entrega. Não calculo “atrasado hoje” com registros históricos.

## Avaliações

Escolho uma avaliação por pedido ordenando os registros por resposta, criação e identificador, com nulos primeiro. O último registro válido fornece a nota; as notas aceitas vão de 1 a 5.

Se o mesmo pedido tiver notas diferentes empatadas nas três chaves de desempate, marco `review_conflict` e deixo a nota nula. Isso evita escolher uma nota arbitrária. `review_id` pode aparecer em mais de um pedido e não é tratado isoladamente como chave única.

A comparação de nota usa apenas elegíveis com nota válida. A proporção de notas baixas considera notas 1 ou 2. As avaliações podem ter ocorrido antes da entrega; o recorte mostra associação, sem medir efeito causal.

## Valores e frete

Produtos, frete e pagamento são campos distintos. O total de produtos e o frete geral somam itens associados a pedidos de **todos os status**. Esses números não são apresentados como faturamento ou receita reconhecida.

A proporção geral de frete é **soma do frete / soma dos produtos**, quando o denominador é positivo. Ela não é a média das proporções individuais. O frete registrado é a cobrança disponível na base, sem equivalência comprovada ao custo da transportadora.

Pedidos sem itens e sem pagamento são contados separadamente. Não exijo que o valor pago seja igual ao valor dos produtos: frete, status e formas de pagamento precisam ser considerados antes de uma conciliação.

## Conferência e repetição da carga

O PostgreSQL recebe um snapshot em uma única transação, protegido por advisory lock. As tabelas são truncadas e recarregadas; o histórico de cargas fica em `olist_meta.loads`. Repetir a carga não acrescenta cópias dos pedidos.

As views SQL reimplementam as regras. Os 21 indicadores gerais são comparados aos resultados pandas: inteiros e centavos exigem igualdade, enquanto números fracionários usam tolerância de 1e-10. Qualquer divergência desfaz a carga inteira. Recortes detalhados não têm comparação automatizada completa entre as duas implementações.

O CI usa uma base sintética com casos de borda. A base real foi processada localmente em pandas; seu snapshot completo ainda deve ser conferido no PostgreSQL. O Power BI também depende de validação no Desktop.

## Limites de interpretação

A cobertura é histórica e tem meses incompletos. Os recortes observados não representam a operação atual nem controlam distância, transportadora, prazo contratado ou composição dos produtos. Comparações por UF usam o destino do cliente; por vendedor usam a presença de seus itens no pedido.

O mínimo de 30 pedidos reduz a presença de grupos muito pequenos, mas não resolve diferenças de composição. Uma investigação operacional precisaria segmentação adicional e dados que esta base não fornece.
