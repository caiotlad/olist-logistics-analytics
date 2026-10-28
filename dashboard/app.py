from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
TABLES = ROOT / "reports" / "tables"


@st.cache_data
def load_snapshot() -> tuple[dict, dict, dict[str, pd.DataFrame], str]:
    generated_overview = GENERATED / "overview.json"
    overview_path = generated_overview if generated_overview.exists() else ROOT / "reports" / "summary.json"
    overview = json.loads(overview_path.read_text(encoding="utf-8"))

    quality_path = GENERATED / "quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    table_dir = GENERATED if generated_overview.exists() else TABLES

    frames: dict[str, pd.DataFrame] = {}
    for name in ("by_month", "by_state", "by_category", "by_review", "by_status"):
        path = table_dir / f"{name}.csv"
        if not path.exists() and table_dir != TABLES:
            path = TABLES / f"{name}.csv"
        frames[name] = pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()

    source = quality.get("source", {}).get("kind", "olist")
    return overview, quality, frames, source


def br_number(value: float | int | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def show_csv_button(frame: pd.DataFrame, filename: str) -> None:
    st.download_button(
        "Baixar recorte CSV",
        data=frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
    )


@st.cache_resource
def load_local_model(path: str) -> dict:
    from joblib import load

    return load(path)


st.set_page_config(
    page_title="Olist Logistics | Analytics",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
      .stApp { background: #f5f7fa; color: #182e47; }
      [data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #dce4ec; border-radius: 12px;
        padding: 16px 18px; box-shadow: 0 2px 8px rgba(24,46,71,.04);
      }
      [data-testid="stMetricLabel"] { color: #5b6f82; }
      h1, h2, h3 { color: #182e47; }
      .eyebrow { color:#176b87; font-size:12px; font-weight:700; letter-spacing:.13em; }
      .source-note { color:#5b6f82; font-size:13px; }
      div[data-testid="stDataFrame"] { border: 1px solid #dce4ec; border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    overview, quality, data, source_kind = load_snapshot()
except (FileNotFoundError, json.JSONDecodeError, pd.errors.ParserError) as error:
    st.error(f"Não consegui abrir o snapshot analítico: {error}")
    st.info("Gere a análise primeiro com `python -m olist_logistics run`.")
    st.stop()

synthetic = source_kind == "synthetic"
source_label = "DEMONSTRAÇÃO · DADOS SINTÉTICOS" if synthetic else "BASE HISTÓRICA OLIST · 2016–2018"
st.markdown(f'<div class="eyebrow">{source_label}</div>', unsafe_allow_html=True)
st.title("Entregas, frete e experiência do cliente")
st.caption("Onde estão os atrasos, como o prazo varia e o que aparece junto às avaliações dos pedidos.")

if synthetic:
    st.warning("Esta demonstração usa dados sintéticos; os números não descrevem a operação da Olist.")
else:
    st.info("Os resultados descrevem esta base histórica. Eles não representam a operação atual da Olist.")

minimum_default = int(quality.get("minimum_group_orders", 30))
minimum = st.sidebar.slider(
    "Mínimo de entregas elegíveis por grupo",
    min_value=5,
    max_value=200,
    value=min(max(minimum_default, 5), 200),
    step=5,
    help="Grupos abaixo do mínimo ficam fora das comparações, mas continuam disponíveis nas tabelas.",
)
st.sidebar.markdown("---")
st.sidebar.markdown("**Fonte**  ")
st.sidebar.caption("Brazilian E-Commerce Public Dataset by Olist")
st.sidebar.caption("Unidade principal: pedido. O cálculo do atraso usa dias de calendário.")

eligible = int(overview.get("eligible_orders", 0))
late = int(overview.get("late_orders", 0))
late_rate = float(overview.get("late_rate", 0))
mean_days = float(overview.get("mean_delivery_days", 0))
p90_days = float(overview.get("p90_delivery_days", 0))
freight_ratio = float(overview.get("freight_to_products_ratio", 0))

cards = st.columns(6)
cards[0].metric("Pedidos", br_number(overview.get("orders")))
cards[1].metric("Entregas elegíveis", br_number(eligible))
cards[2].metric("Atrasos", br_number(late))
cards[3].metric("Taxa de atraso", f"{br_number(late_rate * 100, 2)}%")
cards[4].metric("Prazo médio", f"{br_number(mean_days, 1)} dias")
cards[5].metric("Prazo P90", f"{br_number(p90_days, 1)} dias")

overview_tab, region_tab, category_tab, experience_tab, risk_tab, method_tab = st.tabs(
    ["Visão geral", "Estados", "Categorias", "Experiência", "Risco de atraso", "Método e dados"]
)

with overview_tab:
    left, right = st.columns((1.35, 1))
    monthly = data["by_month"].copy()
    if not monthly.empty:
        monthly = monthly.loc[
            monthly["purchase_month"].ne("UNKNOWN")
            & (monthly["eligible_orders"] >= minimum)
        ].sort_values("purchase_month")
        monthly["taxa_atraso_pct"] = monthly["late_rate"] * 100
    with left:
        st.subheader("Atrasos ao longo do tempo")
        if monthly.empty:
            st.info("Não há meses acima do mínimo selecionado.")
        else:
            st.line_chart(monthly.set_index("purchase_month")[["taxa_atraso_pct"]])
            st.caption("Taxa calculada somente entre pedidos entregues com datas elegíveis.")

    status = data["by_status"].copy()
    with right:
        st.subheader("Pedidos por status")
        if status.empty:
            st.info("Tabela de status indisponível neste snapshot.")
        else:
            status = status.sort_values("orders", ascending=False).head(8)
            st.bar_chart(status.set_index("order_status")[["orders"]])

    st.subheader("Indicadores de contexto")
    context = st.columns(3)
    context[0].metric("Frete / valor dos produtos", f"{br_number(freight_ratio * 100, 1)}%")
    context[1].metric("Entregas excluídas por datas", br_number(overview.get("excluded_delivered_orders")))
    context[2].metric("Pedidos cancelados", br_number(overview.get("canceled_orders")))
    st.caption("Frete / produtos é a razão entre somas registradas; não mede custo da transportadora nem receita líquida.")

with region_tab:
    states = data["by_state"].copy()
    st.subheader("Taxa de atraso por estado de destino")
    if states.empty:
        st.warning("Tabela por estado indisponível neste snapshot.")
    else:
        states["taxa_atraso_pct"] = states["late_rate"] * 100
        eligible_states = states.loc[states["eligible_orders"] >= minimum]
        top = eligible_states.sort_values("late_rate", ascending=False).head(12)
        if top.empty:
            st.info("Nenhum estado atende ao mínimo selecionado.")
        else:
            st.bar_chart(top.set_index("customer_state")[["taxa_atraso_pct"]])
        display = states.sort_values("late_rate", ascending=False).rename(
            columns={
                "customer_state": "Estado",
                "orders": "Pedidos",
                "eligible_orders": "Entregas elegíveis",
                "late_orders": "Atrasos",
                "late_rate": "Taxa de atraso",
                "mean_delivery_days": "Prazo médio (dias)",
                "p90_delivery_days": "Prazo P90 (dias)",
                "mean_review_score": "Nota média",
                "meets_minimum": "Amostra suficiente",
            }
        )
        columns = [name for name in ("Estado", "Pedidos", "Entregas elegíveis", "Atrasos", "Taxa de atraso", "Prazo médio (dias)", "Prazo P90 (dias)", "Nota média", "Amostra suficiente") if name in display]
        display = display[columns]
        display["Amostra suficiente"] = display["Entregas elegíveis"] >= minimum
        display["Taxa de atraso"] = display["Taxa de atraso"] * 100
        st.dataframe(display, hide_index=True, width="stretch", column_config={"Taxa de atraso": st.column_config.NumberColumn(format="%.2f%%")})
        show_csv_button(display, "olist_estados.csv")

with category_tab:
    categories = data["by_category"].copy()
    st.subheader("Atrasos por categoria de produto")
    if categories.empty:
        st.warning("Tabela por categoria indisponível neste snapshot.")
    else:
        categories = categories.loc[categories["eligible_orders"] >= minimum].copy()
        categories["taxa_atraso_pct"] = categories["late_rate"] * 100
        top = categories.sort_values("late_orders", ascending=False).head(12)
        if top.empty:
            st.info("Nenhuma categoria atende ao mínimo selecionado.")
        else:
            st.bar_chart(top.set_index("category")[["taxa_atraso_pct"]])
        display = categories.sort_values("late_orders", ascending=False).rename(
            columns={
                "category": "Categoria",
                "orders": "Pedidos",
                "eligible_orders": "Entregas elegíveis",
                "late_orders": "Atrasos",
                "late_rate": "Taxa de atraso",
                "mean_delivery_days": "Prazo médio (dias)",
                "p90_delivery_days": "Prazo P90 (dias)",
                "mean_review_score": "Nota média",
            }
        )
        columns = [name for name in ("Categoria", "Pedidos", "Entregas elegíveis", "Atrasos", "Taxa de atraso", "Prazo médio (dias)", "Nota média") if name in display]
        display = display[columns]
        display["Taxa de atraso"] = display["Taxa de atraso"] * 100
        st.dataframe(display, hide_index=True, width="stretch", column_config={"Taxa de atraso": st.column_config.NumberColumn(format="%.2f%%")})
        show_csv_button(display, "olist_categorias.csv")

with experience_tab:
    reviews = data["by_review"].copy()
    st.subheader("Nota média por grupo de prazo")
    st.markdown(
        "Pedidos atrasados aparecem associados a avaliações mais baixas nesta base. "
        "Essa comparação histórica não demonstra que o atraso causou a nota."
    )
    if reviews.empty:
        st.warning("Tabela de avaliações indisponível neste snapshot.")
    else:
        score_chart = reviews.set_index("delivery_group")[["mean_review_score"]]
        st.bar_chart(score_chart)
        display = reviews.rename(
            columns={
                "delivery_group": "Grupo de prazo",
                "eligible_orders": "Entregas elegíveis",
                "reviewed_orders": "Pedidos avaliados",
                "mean_review_score": "Nota média",
                "low_score_rate": "Notas 1–2",
            }
        )
        display["Notas 1–2"] = display["Notas 1–2"] * 100
        st.dataframe(display, hide_index=True, width="stretch", column_config={"Notas 1–2": st.column_config.NumberColumn(format="%.2f%%")})

with risk_tab:
    st.subheader("Modelo de classificação de risco")
    ml_metrics_path = ROOT / "reports" / "ml" / "metrics.json"
    if not ml_metrics_path.exists():
        st.info("Gere a avaliação do modelo com `python -m olist_logistics train-delay-model`.")
    else:
        ml_metrics = json.loads(ml_metrics_path.read_text(encoding="utf-8"))
        test_metrics = ml_metrics["test"]["selected_model"]
        validation_rate = ml_metrics["splits"]["validation"]["late_rate"]
        test_rate = ml_metrics["splits"]["test"]["late_rate"]
        test_cards = st.columns(5)
        test_cards[0].metric("Modelo escolhido", ml_metrics["model_selection"]["selected_model"].replace("_", " "))
        test_cards[1].metric("PR-AUC no teste", br_number(test_metrics["average_precision"], 3))
        test_cards[2].metric("Referência", br_number(ml_metrics["test"]["no_skill_average_precision"], 3))
        test_cards[3].metric("ROC-AUC", br_number(test_metrics["roc_auc"], 3))
        test_cards[4].metric("Brier score", br_number(test_metrics["brier_score"], 4))

        top10 = test_metrics["top_10_percent"]
        capacity_cards = st.columns(3)
        capacity_cards[0].metric("Precisão no top 10%", f"{br_number(top10['precision'] * 100, 2)}%")
        capacity_cards[1].metric("Recall no top 10%", f"{br_number(top10['recall'] * 100, 2)}%")
        capacity_cards[2].metric("Lift no top 10%", f"{br_number(top10['lift'], 2)}×")

        rate_change_pp = (test_rate - validation_rate) * 100
        st.warning(
            "Sinal de mudança temporal: a taxa de atraso caiu de "
            f"{br_number(validation_rate * 100, 2)}% na validação para "
            f"{br_number(test_rate * 100, 2)}% no teste ({br_number(rate_change_pp, 2)} pontos percentuais). "
            "O desempenho histórico não comprova validade para a operação atual."
        )

        chart_left, chart_right = st.columns(2)
        precision_recall_image = ROOT / "reports" / "ml" / "precision_recall.png"
        calibration_image = ROOT / "reports" / "ml" / "calibration.png"
        with chart_left:
            if precision_recall_image.exists():
                st.image(str(precision_recall_image), caption="Curva precisão-recall no período de teste")
        with chart_right:
            if calibration_image.exists():
                st.image(str(calibration_image), caption="Calibração no período de teste")

        importance_path = ROOT / "reports" / "ml" / "feature_importance.csv"
        if importance_path.exists():
            st.markdown("#### Atributos usados pelo modelo")
            st.caption("Queda de PR-AUC ao embaralhar cada atributo na validação; mede dependência do modelo, não efeito causal.")
            importance = pd.read_csv(importance_path, encoding="utf-8-sig").head(10)
            importance_labels = {
                "customer_state": "Estado do cliente",
                "promise_lead_days": "Prazo prometido (dias)",
                "same_state_item_share": "Itens no mesmo estado",
                "installments_mean": "Parcelas médias",
                "dominant_seller_state": "Estado do vendedor predominante",
                "mean_item_freight_brl": "Frete médio por item (R$)",
                "mean_item_price_brl": "Preço médio por item (R$)",
                "installments_max": "Parcelas máximas",
                "approval_wait_minutes": "Minutos até aprovação",
                "seller_count": "Número de vendedores",
            }
            importance["atributo"] = importance["feature"].map(importance_labels).fillna(importance["feature"])
            importance = importance.set_index("atributo")
            st.bar_chart(importance[["average_precision_decrease"]])

        st.markdown("#### Simulador local")
        st.caption("O formulário usa atributos gerais de um pedido e não solicita IDs ou dados pessoais.")
        model_path = ROOT / ".work" / "ml" / "delay-risk.joblib"
        if not model_path.exists():
            st.info("Para habilitar o simulador neste computador, instale `.[ml]` e execute `python -m olist_logistics train-delay-model`.")
        else:
            try:
                artifact = load_local_model(str(model_path))
                category_values = artifact["categorical_values"]
                with st.form("delay_risk_simulator"):
                    st.markdown("**Rota e calendário**")
                    route = st.columns(3)
                    customer_state = route[0].selectbox("Estado do cliente", category_values["customer_state"])
                    seller_state = route[1].selectbox("Estado do vendedor predominante", category_values["dominant_seller_state"])
                    category = route[2].selectbox("Categoria predominante", category_values["dominant_category"])
                    payment_and_time = st.columns(4)
                    payment_type = payment_and_time[0].selectbox("Pagamento", category_values["dominant_payment_type"])
                    month = payment_and_time[1].selectbox("Mês da compra", category_values["purchase_month"])
                    weekday = payment_and_time[2].selectbox(
                        "Dia da semana",
                        category_values["purchase_weekday"],
                        format_func=lambda value: ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")[int(value)] if str(value).isdigit() and 0 <= int(value) <= 6 else str(value),
                    )
                    purchase_hour = payment_and_time[3].slider("Hora", 0, 23, 12)

                    st.markdown("**Prazo e composição do pedido**")
                    order = st.columns(4)
                    promise_lead_days = order[0].number_input("Prazo prometido (dias)", min_value=1.0, max_value=90.0, value=15.0, step=1.0)
                    approval_wait_minutes = order[1].number_input("Tempo até aprovação (min)", min_value=0.0, max_value=10080.0, value=15.0, step=5.0)
                    item_count = order[2].number_input("Itens", min_value=1, max_value=50, value=1, step=1)
                    seller_count = order[3].number_input("Vendedores", min_value=1, max_value=20, value=1, step=1)
                    order2 = st.columns(4)
                    category_count = order2[0].number_input("Categorias distintas", min_value=1, max_value=30, value=1, step=1)
                    seller_state_count = order2[1].number_input("Estados vendedores", min_value=1, max_value=20, value=1, step=1)
                    same_state_item_share = order2[2].slider("Itens no mesmo estado", 0.0, 1.0, 0.5, 0.05)
                    installments = order2[3].number_input("Parcelas", min_value=0, max_value=24, value=1, step=1)
                    order3 = st.columns(3)
                    product_total_brl = order3[0].number_input("Valor dos produtos (R$)", min_value=0.0, max_value=100000.0, value=200.0, step=10.0)
                    freight_total_brl = order3[1].number_input("Frete (R$)", min_value=0.0, max_value=20000.0, value=30.0, step=5.0)
                    payment_count = order3[2].number_input("Pagamentos registrados", min_value=1, max_value=20, value=1, step=1)
                    submitted = st.form_submit_button("Calcular risco histórico")

                if submitted:
                    divisor = max(int(item_count), 1)
                    feature_values = {
                        "customer_state": customer_state,
                        "dominant_seller_state": seller_state,
                        "dominant_category": category,
                        "dominant_payment_type": payment_type,
                        "purchase_month": month,
                        "purchase_weekday": weekday,
                        "purchase_hour": float(purchase_hour),
                        "approval_wait_minutes": float(approval_wait_minutes),
                        "promise_lead_days": float(promise_lead_days),
                        "item_count": int(item_count),
                        "seller_count": min(int(seller_count), int(item_count)),
                        "category_count": min(int(category_count), int(item_count)),
                        "seller_state_count": min(int(seller_state_count), int(seller_count), int(item_count)),
                        "same_state_item_share": float(same_state_item_share),
                        "product_total_brl": float(product_total_brl),
                        "freight_total_brl": float(freight_total_brl),
                        "mean_item_price_brl": float(product_total_brl) / divisor,
                        "mean_item_freight_brl": float(freight_total_brl) / divisor,
                        "freight_to_products_ratio": float(freight_total_brl / product_total_brl) if product_total_brl else 0.0,
                        "payment_count": int(payment_count),
                        "installments_max": int(installments),
                        "installments_mean": float(installments),
                    }
                    model_input = pd.DataFrame([feature_values], columns=artifact["features"])
                    probability = float(artifact["pipeline"].predict_proba(model_input)[0, 1])
                    threshold = float(artifact["threshold"])
                    st.metric("Risco estimado no modelo histórico", f"{br_number(probability * 100, 2)}%")
                    if probability >= threshold:
                        st.warning(f"Acima do limiar histórico de validação ({br_number(threshold * 100, 2)}%).")
                    else:
                        st.success(f"Abaixo do limiar histórico de validação ({br_number(threshold * 100, 2)}%).")
                    st.caption("Exercício demonstrativo: esta probabilidade não é calibrada nem validada para a operação atual.")
            except (ImportError, OSError, KeyError, ValueError) as error:
                st.error(f"Não consegui carregar o modelo local: {error}")

with method_tab:
    st.subheader("Como ler os indicadores")
    start = overview.get("purchase_start", "—")
    end = overview.get("purchase_end", "—")
    st.write(f"**Período de compra:** {start[:10]} a {end[:10]}.")
    st.write(f"**Pedidos na base:** {br_number(overview.get('orders'))} · **entregues:** {br_number(overview.get('delivered_orders'))} · **elegíveis para prazo:** {br_number(eligible)}.")
    st.write(f"**Excluídos do denominador de atraso:** {br_number(overview.get('excluded_delivered_orders'))} entregas por datas ausentes ou incoerentes.")
    st.markdown(
        "- Atraso compara datas de calendário; uma entrega no dia prometido fica no prazo.\n"
        "- O prazo em dias usa a diferença entre timestamps.\n"
        "- Cancelados e pedidos sem datas suficientes não entram na taxa de atraso.\n"
        "- Itens e pagamentos são agregados separadamente para evitar multiplicar valores em junções.\n"
        "- Comparações por grupo respeitam o mínimo ajustável na barra lateral."
    )
    st.subheader("Rastreabilidade")
    st.write("Fonte: Olist, Brazilian E-Commerce Public Dataset, disponibilizada no Kaggle sob licença CC BY-NC-SA 4.0.")
    st.write("Os CSVs brutos não são necessários para abrir este painel; ele usa somente os resumos analíticos do projeto.")
    st.markdown(
        "[Análise metodológica](https://github.com/caiotlad/olist-logistics-analytics/blob/main/reports/findings.md) · "
        "[Fonte e licença](https://github.com/caiotlad/olist-logistics-analytics/blob/main/DATA_SOURCES.md)"
    )
