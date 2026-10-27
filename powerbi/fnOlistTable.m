// Crie uma consulta em branco chamada fnOlistTable e cole esta função.
// As credenciais são informadas no conector, nunca neste arquivo.
(Server as text, Database as text, TableName as text) as table =>
let
    Allowed = {"fact_orders", "seller_orders", "category_orders", "calendar"},
    Validated =
        if List.Contains(Allowed, TableName) then TableName
        else error "Mart não permitido.",
    Source = PostgreSQL.Database(
        Server, Database,
        [CreateNavigationProperties = false, CommandTimeout = #duration(0, 0, 5, 0)]
    ),
    Data = Source{[Schema = "olist_mart", Item = Validated]}[Data],
    Typed =
        if Validated = "calendar" then
            Table.TransformColumnTypes(Data, {
                {"date", type date}, {"year", Int64.Type},
                {"month", Int64.Type}, {"year_month", type text}
            })
        else
            Table.TransformColumnTypes(Data, {
                {"purchase_date", type date},
                {"delivery_eligible", type logical},
                {"delivered_late", type logical},
                {"product_total_cents", Int64.Type},
                {"freight_total_cents", Int64.Type},
                {"review_score", Int64.Type},
                {"delivery_days", type number}
            })
in
    Typed
