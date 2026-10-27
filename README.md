# Olist Logistics

Neste projeto, quero investigar o desempenho das entregas de um com�rcio eletr�nico e entender onde se concentram os atrasos. Meu interesse � ligar a an�lise a decis�es de opera��o: quais grupos precisam de aten��o e o que os dados permitem concluir.

**Situa��o:** planejamento. A base ainda n�o foi baixada nem analisada.

## Fonte e perguntas

Vou usar o [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). � uma base hist�rica; as conclus�es ser�o limitadas ao per�odo e � cobertura dos arquivos.

As perguntas iniciais s�o:

- Qual � a propor��o de pedidos entregues depois do prazo estimado?
- Como o tempo de entrega varia entre regi�es, vendedores e categorias?
- Qual � a rela��o entre atraso e avalia��o do pedido?
- Como o frete se distribui em rela��o ao valor dos produtos?

Antes de responder, vou conferir os campos dispon�veis, as datas, os registros ausentes e os relacionamentos entre as tabelas.

## Como pretendo organizar a an�lise

Vou usar Python e pandas para a inspe��o inicial, PostgreSQL para a base anal�tica e SQL para calcular os indicadores. O dashboard ser� feito no Power BI.

A unidade de an�lise principal ser� o pedido. Como um pedido pode ter v�rios itens e pagamentos, vou agregar essas tabelas antes de combin�-las. Isso � necess�rio para n�o inflar valores e contagens.

Vou documentar quem entra em cada indicador, como os cancelamentos ser�o tratados e o que fazer quando uma data estiver ausente. Compara��es por vendedor ou regi�o tamb�m precisar�o mostrar a quantidade de pedidos observados.

## Etapas planejadas

1. Registrar a origem, a licen�a e o dicion�rio dos arquivos.
2. Avaliar completude, duplicidades, chaves e coer�ncia das datas.
3. Carregar os dados e construir as tabelas anal�ticas.
4. Escrever as consultas dos indicadores e conferir os totais.
5. Fazer a an�lise explorat�ria e montar o dashboard.
6. Produzir um relat�rio curto com evid�ncias, limita��es e recomenda��es.

## Como vou considerar a primeira vers�o pronta

O reposit�rio dever� permitir reproduzir a carga e as m�tricas. O dashboard ter� prazo, atraso, frete e avalia��es, com filtros compat�veis com os dados. O relat�rio dever� responder �s perguntas que a base permitir responder, incluindo resultados que contrariem minhas hip�teses.

N�o vou apresentar correla��o como causa. Tamb�m n�o vou usar esta base hist�rica para descrever a opera��o atual da Olist.

## Entreg�veis previstos

Scripts de prepara��o, consultas SQL, dicion�rio dos indicadores, dashboard e relat�rio. Arquivos grandes ficar�o fora do Git; vou deixar instru��es para obter a base na origem e respeitar seus termos de uso.
