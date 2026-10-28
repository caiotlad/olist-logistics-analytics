# Olist Delivery Risk — cartão do modelo

## Objetivo

Estimar o risco de atraso de um pedido após a aprovação, para priorizar análise e eventual contato proativo. O painel é uma demonstração histórica de portfólio, não uma ferramenta operacional da Olist.

## Alvo e população

1 quando a data de entrega ao cliente é posterior à data estimada, comparando dias de calendário; 0 nos demais pedidos elegíveis.

O conjunto rotulado contém 96.470 pedidos entregues elegíveis, dos quais 6.534 atrasaram (6,77%). Pedidos cancelados, não entregues e entregues sem datas coerentes não recebem rótulo neste estudo.

## Desenho de validação

- Treino: compras anteriores a 2018-01-01.
- Validação: compras de 2018-01-01 a 2018-06-30.
- Teste final: compras a partir de 2018-07-01.
- O candidato foi escolhido por PR-AUC na validação temporal; o limiar que maximiza F1 também foi escolhido na validação. O teste não participa dessas escolhas.

## Resultado no teste

- Modelo selecionado: `logistic_regression`.
- PR-AUC: 0.0784; referência sem habilidade: 0.0481.
- ROC-AUC: 0.6418.
- Brier score: 0.0456 (menor é melhor para a calibração probabilística).
- Brier do baseline de prevalência: 0.0458; a melhora absoluta é pequena.
- Precisão nos 10% de maior risco: 6.79%; recall: 14.14%; lift: 1.41×.

Na validação, a taxa de atraso foi 8,63% e a PR-AUC foi 0.1832. No teste, a prevalência caiu para 4,81% e a PR-AUC foi 0.0784. Essa mudança temporal limita a estabilidade do modelo. A curva de calibração também mostra excesso de previsão no grupo de maior risco.

## Prevenção de vazamento

O modelo não recebe identificadores de pedido/cliente/vendedor, avaliações, data real de despacho ou data real de entrega. Usa somente atributos de compra, pagamento, destino, itens e prazo estimado que estão disponíveis até a aprovação.

## Limitações

Os dados cobrem 2016–2018. Mudanças em transportadoras, catálogo, regiões, prazos e comportamento de compra podem invalidar o desempenho. A avaliação não prova causalidade, economia, nem validade para a operação atual. A população de treino inclui apenas pedidos entregues e elegíveis.

## Artefatos

- `metrics.json`: métricas, janelas e hashes das fontes.
- `model_selection.csv`: comparação dos candidatos na validação.
- `feature_importance.csv` e `permutation_importance.png`: interpretação por permutação, calculada na validação.
- `precision_recall.png` e `calibration.png`: diagnóstico no teste final.
- O pipeline serializado fica no caminho local configurado e não é publicado junto aos dados brutos.
