# Origem e atribuição

Usei o **Brazilian E-Commerce Public Dataset by Olist**, publicado pela Olist no [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

A página da fonte informa a licença [Creative Commons Atribuição–NãoComercial–CompartilhaIgual 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Os agregados, gráficos e relatórios derivados da base neste repositório são disponibilizados sob essa mesma licença, com esta atribuição. O uso é de estudo e portfólio; a licença da base também deve ser observada em reutilizações.

O código e a documentação de implementação têm licença MIT, descrita em LICENSE. Essa licença não substitui os termos da base nem dos resultados dela derivados.

## Identificação da execução publicada

- Arquivo recebido: `archive.zip`, 44.717.580 bytes.
- SHA-256 do ZIP: `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`.
- Importação e análise: 27 de outubro de 2026, UTC.
- Cobertura de compra observada: 4 de setembro de 2016 a 17 de outubro de 2018.
- Os hashes identificam os bytes analisados; não equivalem a uma assinatura de autenticidade da origem.
- Não redistribuo o ZIP nem os CSVs brutos no repositório.

| Arquivo | Linhas |
| --- | ---: |
| olist_orders_dataset.csv | 99.441 |
| olist_customers_dataset.csv | 99.441 |
| olist_order_items_dataset.csv | 112.650 |
| olist_order_payments_dataset.csv | 103.886 |
| olist_order_reviews_dataset.csv | 99.224 |
| olist_products_dataset.csv | 32.951 |
| olist_sellers_dataset.csv | 3.095 |
| product_category_name_translation.csv | 71 |

A geolocalização não é importada. A tradução de categorias é validada como fonte auxiliar; os agrupamentos analíticos usam o identificador original em português.

O [manifesto publicado](reports/source_manifest.json) registra os hashes de cada CSV, os perfis de campos ausentes e o resultado das validações. A importação local gera `data/raw/SOURCE.json` e cada execução gera seu próprio `quality.json`.
