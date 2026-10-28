# Modelo de risco de atraso — método

## Pergunta de negócio

Após a aprovação de um pedido, quais pedidos históricos têm maior risco de ultrapassar a data prometida? Um escore poderia ajudar a priorizar uma análise ou um contato proativo, mas o projeto não estima economia nem efeito causal.

## Unidade, população e alvo

A unidade é o pedido. O conjunto rotulado contém pedidos com status `delivered`, compra, entrega e estimativa presentes, entrega posterior ou igual à compra e estimativa não anterior ao dia da compra. O alvo compara datas de calendário: `delivered_late = 1` quando `order_delivered_customer_date.date > order_estimated_delivery_date.date`.

Pedidos cancelados, ainda não entregues, sem data de entrega ou com cronologia incoerente ficam fora do treino por não terem um rótulo comparável. Essa população condiciona a interpretação: o modelo estima risco de atraso entre pedidos históricos que acabaram entregues e eram elegíveis.

## Momento de previsão e atributos

O escore é definido para o momento após a aprovação. São usados atributos que podem existir até então: estado de destino e do vendedor predominante, categoria predominante, tipo de pagamento, parcelas, quantidade de itens/vendedores/categorias, valores agregados de produtos/frete, participação de itens vendidos no mesmo estado, horário/dia/mês da compra, minutos até a aprovação e dias prometidos.

Não entram IDs de pedido, cliente, vendedor ou produto; avaliação; data de despacho real; data de entrega real; nem duração de entrega ou atraso calculados. A estimativa de entrega entra somente como prazo prometido relativo à compra, uma informação disponível quando o prazo é apresentado.

## Separação temporal e seleção

Os pedidos são ordenados pelo horário de compra:

| Conjunto | Janela |
| --- | --- |
| Treino | Antes de 2018-01-01 |
| Validação | 2018-01-01 até 2018-06-30 |
| Teste final | A partir de 2018-07-01 |

O baseline de referência prevê a prevalência de atraso do treino. Regressão logística e HistGradientBoosting usam o mesmo pipeline de imputação e one-hot encoding, ajustado apenas no treino. O melhor candidato é escolhido pela average precision na validação. O limiar que maximiza F1 também é escolhido na validação. O teste final não participa dessas escolhas.

## Métricas

- **Average precision / PR-AUC:** métrica principal para a classe rara; compare com a prevalência no teste.
- **Precisão, recall e lift no top 10%:** cenário transparente de capacidade para priorizar uma fração dos pedidos. Não representa política operacional recomendada.
- **Brier score e curva de calibração:** avaliam a qualidade das probabilidades, além da ordenação.
- **ROC-AUC:** medida complementar, não substitui a análise de precisão-recall.

Não se usa acurácia como métrica principal: uma regra que classificasse todos os pedidos como “no prazo” teria cerca de 93% de acurácia nesta base e não encontraria nenhum atraso.

## Fundamentos de ML demonstrados

- Transformar uma pergunta operacional em um alvo binário e declarar a população para a qual ele vale.
- Criar atributos a partir de várias tabelas sem multiplicar linhas do pedido.
- Separar treino, validação e teste por tempo; manter o teste fora da escolha de modelo e limiar.
- Ajustar imputação e one-hot encoding dentro do pipeline treinado somente no período de treino.
- Comparar um baseline de prevalência com modelos de classificação e tratar o desbalanceamento pelas métricas e pela capacidade de priorização.
- Escolher um limiar na validação, medir calibração e explicar a importância das variáveis sem interpretar importância como causalidade.
- Registrar hashes das fontes, métricas, limites da análise e sinal de mudança temporal.

## Execução e artefatos

```powershell
python -m pip install -e ".[ml]"
python -m olist_logistics train-delay-model
```

O processo grava métricas, comparação dos modelos, importância por permutação calculada na validação, curvas do teste final e um cartão do modelo em `reports/ml/`. O pipeline treinado é salvo localmente em `.work/ml/delay-risk.joblib`; não é preciso versionar esse binário para reproduzir o treino.

No snapshot atual, a regressão logística foi selecionada na validação. No teste de julho–agosto de 2018, sua PR-AUC foi 0,0784 contra uma prevalência de 0,0481; o lift no top 10% foi 1,41×. A taxa de atraso mudou de 8,63% na validação para 4,81% no teste e a PR-AUC caiu de 0,1832 para 0,0784. Essa diferença evidencia mudança temporal e limita a leitura do resultado como capacidade estável.

Os valores completos e hashes das fontes estão em [`reports/ml/metrics.json`](../reports/ml/metrics.json), junto com o [cartão do modelo](../reports/ml/model_card.md), a [curva precisão-recall](../reports/ml/precision_recall.png), a [calibração](../reports/ml/calibration.png) e a [importância por permutação](../reports/ml/permutation_importance.png).

## Limitações

A base cobre 2016–2018, antes de mudanças operacionais posteriores. O teste é temporal dentro da mesma fonte e não comprova desempenho atual. Pedidos ainda não entregues não têm rótulo final nesta base. O dataset não inclui custos de intervenção, por isso não se afirma ROI. Uma implantação exigiria treino com dados recentes, monitoramento de qualidade e drift, calibração e validação operacional.
