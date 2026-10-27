import base64
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from .contracts import DATA_LICENSE, SOURCE_URL


def _display(value, kind="number"):
    if value is None:
        return "Não disponível"
    if kind == "percent":
        return f"{value * 100:.1f}%"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return f"{value:.2f}"


def _save_chart(output, filename, title, labels, values, percentage=False, horizontal=False, max_value=None):
    fig, ax = plt.subplots(figsize=(10.5, 5.2), layout="constrained")
    fig.patch.set_facecolor("#f7f8fa")
    ax.set_facecolor("#f7f8fa")
    usable = [(str(label), float(value)) for label, value in zip(labels, values) if value is not None and math.isfinite(float(value))]
    if usable:
        labels, values = zip(*usable)
        if horizontal:
            ax.barh(labels, values, color="#176b87", height=0.65)
            ax.invert_yaxis()
            if percentage:
                ax.xaxis.set_major_formatter(PercentFormatter(1))
        else:
            ax.bar(labels, values, color="#176b87", width=0.65)
            if percentage:
                ax.yaxis.set_major_formatter(PercentFormatter(1))
            if len(labels) > 8:
                ax.tick_params(axis="x", labelrotation=65)
    else:
        ax.text(0.5, 0.5, "Dados insuficientes para este recorte", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
    if max_value is not None and not horizontal:
        ax.set_ylim(0, max_value)
    ax.set_title(title, loc="left", fontsize=14, color="#172c42", pad=18)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x" if horizontal else "y", alpha=0.15)
    ax.set_axisbelow(True)
    path = output / filename
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def _table(frame, limit=15):
    return frame.head(limit).to_html(index=False, border=0, classes="data-table", na_rep="Não disponível", float_format=lambda x: f"{x:.4f}")


def write_report(output, summary, quality, source):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    values = summary["overview"]
    synthetic = source.get("kind") == "synthetic"
    label = "DEMONSTRAÇÃO — DADOS SINTÉTICOS" if synthetic else "BASE HISTÓRICA — ARQUIVOS IMPORTADOS"
    charts = []
    states = summary["by_state"]
    selected = states.loc[states["meets_minimum"]].sort_values("late_rate", ascending=False).head(12)
    charts.append(_save_chart(
        output, "late_by_state.png", "Atrasos por estado de destino — grupos com amostra mínima",
        [f"{r.customer_state} · n={r.eligible_orders}" for r in selected.itertuples()],
        selected["late_rate"].tolist(), percentage=True, horizontal=True,
    ))
    monthly = summary["by_month"]
    monthly = monthly.loc[monthly["purchase_month"].ne("UNKNOWN") & monthly["meets_minimum"]].sort_values("purchase_month")
    charts.append(_save_chart(
        output, "late_by_month.png", f"Taxa de atraso por mês · mínimo de {quality['minimum_group_orders']} entregas",
        monthly["purchase_month"].tolist(), monthly["late_rate"].tolist(), percentage=True,
    ))
    reviews = summary["by_review"]
    charts.append(_save_chart(
        output, "reviews_by_delivery.png", "Nota média da última avaliação válida por pedido",
        [f"{r.delivery_group} · n={r.reviewed_orders}" for r in reviews.itertuples()],
        reviews["mean_review_score"].tolist(), max_value=5,
    ))
    charts.append(_save_chart(
        output, "orders_by_status.png", "Pedidos por situação registrada na base",
        summary["by_status"]["order_status"].tolist(), summary["by_status"]["orders"].tolist(),
    ))
    cards = [
        ("Pedidos", _display(values["orders"])),
        ("Entregas elegíveis", _display(values["eligible_orders"])),
        ("Com atraso", _display(values["late_orders"])),
        ("Taxa de atraso", _display(values["late_rate"], "percent")),
        ("Prazo médio", _display(values["mean_delivery_days"]) + " dias"),
        ("P90 do prazo", _display(values["p90_delivery_days"]) + " dias"),
    ]
    note = (
        "Estes registros foram criados para testar o pipeline. Os números não descrevem a Olist."
        if synthetic else
        "A base é histórica. Os resultados descrevem os arquivos desta execução e não a operação atual da Olist."
    )
    image_html = "".join(
        '<figure><img alt="' + html.escape(chart.stem) + '" src="data:image/png;base64,'
        + base64.b64encode(chart.read_bytes()).decode("ascii") + '"></figure>'
        for chart in charts
    )
    card_html = "".join('<div class="card"><span>' + html.escape(title) + '</span><strong>' + html.escape(value) + '</strong></div>' for title, value in cards)
    content = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Olist Logistics — relatório</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f8fa;color:#172c42;font:15px/1.55 system-ui,sans-serif}
main{max-width:1280px;margin:auto;padding:40px 32px}header{border-top:5px solid #176b87;padding:22px 0}
h1{font-size:34px;margin:8px 0}h2{font-size:23px;margin-top:32px}.eyebrow{letter-spacing:.12em;font-size:12px;font-weight:700}
.notice{background:#fff4d7;border-left:4px solid #a36f00;padding:16px;margin:18px 0}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:#fff;border:1px solid #dae0e7;padding:20px}
.card span{display:block;color:#53677c;font-size:13px}.card strong{font-size:28px}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:white}img{display:block;width:100%;height:auto}
.table-wrap{overflow:auto}.data-table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #e0e6ec}th{background:#eaf0f5}
footer{margin-top:30px;border-top:1px solid #d5dee7;padding-top:18px;font-size:12px;color:#53677c}
@media(max-width:800px){main{padding:20px}.cards,.charts{grid-template-columns:1fr}}
</style><main>"""
    content += '<header><div class="eyebrow">' + html.escape(label) + '</div><h1>Entregas, frete e experiência do cliente</h1>'
    content += '<p>Olist Logistics · Caio Teixeira Ladeira</p></header><div class="notice">' + html.escape(note) + '</div>'
    content += '<section class="cards">' + card_html + '</section>'
    content += "<p>Elegíveis: status entregue, datas presentes e cronologia coerente. Atraso é medido por dia de calendário; entrega no dia prometido é considerada no prazo.</p>"
    content += "<p>Entregas excluídas por datas ausentes ou incoerentes: <strong>" + str(values["excluded_delivered_orders"]) + "</strong>.</p>"
    content += '<section class="charts">' + image_html + '</section>'
    content += "<h2>Estado de destino</h2><p>Amostras pequenas permanecem nos CSVs, mas não entram no gráfico de comparação.</p><div class='table-wrap'>" + _table(states.sort_values("eligible_orders", ascending=False), 30) + "</div>"
    content += "<h2>Avaliações e entrega</h2><p>A associação observada não demonstra que o atraso causou a nota. A avaliação pode ter sido respondida antes da entrega.</p><div class='table-wrap'>" + _table(reviews) + "</div>"
    content += "<h2>Frete registrado</h2><p>Frete / valor dos produtos: <strong>" + _display(values["freight_to_products_ratio"], "percent") + "</strong>. Razão entre somas, considerando os registros com itens de todos os status. Não representa custo da transportadora nem receita líquida.</p>"
    content += "<h2>Qualidade e rastreabilidade</h2><p>Os arquivos de auditoria incluem quantidade de linhas, campos ausentes, hashes SHA-256 e regras aplicadas.</p>"
    content += "<footer>Fonte declarada: <a href='" + SOURCE_URL + "'>Brazilian E-Commerce Public Dataset by Olist</a> · Licença da base: " + DATA_LICENSE + "."
    content += "<br>Saídas derivadas da base real devem preservar atribuição e as condições da licença. Dados sintéticos foram criados neste projeto.</footer></main></html>"
    (output / "report.html").write_text(content, encoding="utf-8")
    text = "# Olist Logistics — resumo da execução\\n\\n"
    text += label + "\\n\\n" + note + "\\n\\n"
    text += f"Pedidos: {values['orders']}. Entregas elegíveis: {values['eligible_orders']}. Atrasos: {values['late_orders']}. "
    text += "Taxa de atraso: " + _display(values["late_rate"], "percent") + ".\\n\\n"
    text += f"Entregas excluídas: {values['excluded_delivered_orders']}. Prazo médio: {_display(values['mean_delivery_days'])} dias. "
    text += f"P90: {_display(values['p90_delivery_days'])} dias.\\n\\n"
    text += "A análise por vendedor considera pedidos com participação desse vendedor. O conjunto não informa uma data de entrega por item, então o atraso do pedido não identifica o responsável.\\n\\n"
    text += "Comparações de notas são associações históricas. Não há identificação causal. Pedidos não entregues ficam fora do denominador da taxa de atraso.\\n"
    (output / "summary.md").write_text(text.replace("\\n", "\n"), encoding="utf-8")
    (output / "overview.json").write_text(json.dumps(values, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for name, frame in summary.items():
        if name != "overview":
            frame.to_csv(output / (name + ".csv"), index=False, encoding="utf-8-sig")
    return output / "report.html"
